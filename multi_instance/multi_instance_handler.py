
import asyncio
import json
import time
from typing import AsyncGenerator

from fastapi import HTTPException
from starlette.requests import Request

from api_utils.utils import prepare_combined_prompt
from browser_utils.page_controller import PageController
from instance_manager import PageManager
from logger_config import logger
from models import ChatCompletionRequest, ClientDisconnectedError

async def process_request_on_instance(request_id: str, request: ChatCompletionRequest, page_manager: PageManager) -> AsyncGenerator[str, None]:
    """
    在单个实例上处理请求，并以流式响应返回结果。
    This function is refactored to align with the single-instance processing flow.
    """
    start_time = time.time()
    try:
        async with page_manager.get_page(request_id) as page_info:
            if not page_info:
                raise RuntimeError("Failed to acquire a page from the manager.")
                
            instance_id = page_info["id"]
            page = page_info["page"]
            
            logger.info(f"[{request_id}][{instance_id}] [Multi-Instance-Flow] 1. Acquired page instance.")

            # Initialize PageController
            page_controller = PageController(page, logger, request_id, instance_id)
            
            # Simplified disconnect check for this flow
            check_client_disconnected = lambda stage: False

            # Aligning with single-instance flow: Step 1 - Clear chat history
            logger.info(f"[{request_id}][{instance_id}] [Multi-Instance-Flow] 2. Clearing chat history...")
            await page_controller.clear_chat_history(check_client_disconnected)
            logger.info(f"[{request_id}][{instance_id}] [Multi-Instance-Flow] Chat history cleared.")

            # Aligning with single-instance flow: Step 2 - Prepare prompt
            logger.info(f"[{request_id}][{instance_id}] [Multi-Instance-Flow] 3. Preparing combined prompt...")
            combined_prompt, _ = prepare_combined_prompt(request.messages, request.tools, request_id)
            logger.info(f"[{request_id}][{instance_id}] [Multi-Instance-Flow] Prompt prepared, length: {len(combined_prompt)}")

            # Parameters are managed by the page's default state in multi-instance mode for now.

            # Aligning with single-instance flow: Step 3 - Submit prompt
            logger.info(f"[{request_id}][{instance_id}] [Multi-Instance-Flow] 4. Submitting prompt...")
            submit_success = await page_controller.submit_prompt(
                prompt=combined_prompt,
                image_list=[],
                check_client_disconnected=check_client_disconnected
            )
            if not submit_success:
                error_detail = f"[{request_id}][{instance_id}] Failed to submit prompt."
                logger.error(error_detail)
                yield f"data: {json.dumps({'error': {'message': error_detail, 'code': 500}})}\n\n"
                yield f"data: [DONE]\n\n"
                return

            logger.info(f"[{request_id}][{instance_id}] [Multi-Instance-Flow] Prompt submission successful.")

            # Aligning with single-instance flow: Step 4 - Get response
            logger.info(f"[{request_id}][{instance_id}] [Multi-Instance-Flow] 5. Waiting for and getting response...")
            final_response = await page_controller.get_response(check_client_disconnected)
            logger.info(f"[{request_id}][{instance_id}] [Multi-Instance-Flow] 6. Successfully got response, length: {len(final_response)}")

            # Stream the final result back
            yield f"data: {json.dumps({'text': final_response})}\n\n"
            yield f"data: [DONE]\n\n"

    except ClientDisconnectedError as e:
        logger.warning(f"[{request_id}] Client disconnected in multi-instance handler: {e}")
    except Exception as e:
        error_message = f"[{request_id}] An unexpected error occurred in multi-instance handler: {e}"
        logger.error(error_message, exc_info=True)
        try:
            yield f"data: {json.dumps({'error': {'message': str(e), 'code': 500}})}\n\n"
            yield f"data: [DONE]\n\n"
        except Exception as yield_error:
            logger.error(f"[{request_id}] Failed to yield error to client: {yield_error}")
    finally:
        end_time = time.time()
        logger.info(f"[{request_id}] Multi-instance request finished in {end_time - start_time:.2f} seconds.")

async def multi_instance_chat_completions(request: ChatCompletionRequest, http_request: Request):
    """
    Entry point for multi-instance chat completions.
    It picks an available browser instance and forwards the request.
    """
    from server import page_manager, request_queue, queue_semaphore, active_requests

    request_id = f"mi-{int(time.time() * 1000)}-{request.messages[-1].content[:16]}"
    
    # Use the queueing mechanism
    queue_item = (request, http_request, request_id)
    await request_queue.put(queue_item)
    queue_semaphore.release()
    
    logger.info(f"[{request_id}] Request queued. Current queue size: {request_queue.qsize()}")
    
    # Wait for the response to be generated by the worker
    response_generator = active_requests.get(request_id)
    if response_generator:
        return StreamingResponse(response_generator, media_type="text/event-stream")
    else:
        # This part should ideally wait for the response to be available.
        # For now, we assume the worker will place it in active_requests.
        # A more robust solution might involve a Future or an Event.
        
        # Let's wait a moment for the worker to pick it up
        await asyncio.sleep(1) 
        response_generator = active_requests.get(request_id)
        if response_generator:
             return StreamingResponse(response_generator, media_type="text/event-stream")
        else:
            logger.error(f"[{request_id}] Could not find response generator in active_requests.")
            return HTTPException(status_code=500, detail="Failed to process request.")
