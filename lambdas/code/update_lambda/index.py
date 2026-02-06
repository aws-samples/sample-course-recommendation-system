import json
import boto3
import os
import logging
import cfnresponse
import time

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Lambda client
lambda_client = boto3.client('lambda')

def handler(event, context):
    """
    Custom resource handler for updating Lambda environment variables
    """
    # Extract properties
    function_name = event.get('ResourceProperties', {}).get('FunctionName')
    agent_id = event.get('ResourceProperties', {}).get('AgentId')
    agent_alias_id = event.get('ResourceProperties', {}).get('AgentAliasId')
    
    # Initialize response data
    response_data = {}
    physical_id = f"update-lambda-{function_name}"
    
    try:
        request_type = event['RequestType']
        
        if request_type == 'Create' or request_type == 'Update':
            # Update Lambda environment variables
            if function_name and agent_id and agent_alias_id:
                # Wait for agent IDs to be available (they might be tokens that need to be resolved)
                max_attempts = 10
                delay = 10
                for attempt in range(max_attempts):
                    if agent_id.startswith('${Token[') or agent_alias_id.startswith('${Token['):
                        logger.info(f"Agent IDs not yet available, waiting... (attempt {attempt+1}/{max_attempts})")
                        time.sleep(delay)
                    else:
                        break
                
                # Update Lambda environment variables
                update_lambda_environment(function_name, agent_id, agent_alias_id)
                response_data = {
                    'FunctionName': function_name,
                    'AgentId': agent_id,
                    'AgentAliasId': agent_alias_id
                }
            else:
                logger.error("Missing required properties")
                cfnresponse.send(event, context, cfnresponse.FAILED, {}, physical_id, reason="Missing required properties")
                return
        
        # Send success response
        cfnresponse.send(event, context, cfnresponse.SUCCESS, response_data, physical_id)
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        cfnresponse.send(event, context, cfnresponse.FAILED, {}, physical_id, reason=str(e))

def update_lambda_environment(function_name, agent_id, agent_alias_id):
    """
    Update Lambda environment variables with agent IDs
    """
    try:
        # Get current configuration
        response = lambda_client.get_function_configuration(
            FunctionName=function_name
        )
        
        # Get current environment variables
        current_env = response.get('Environment', {}).get('Variables', {})
        
        # Update environment variables
        new_env = dict(current_env)  # Create a copy to avoid modifying the original
        new_env['AGENT_ID'] = agent_id
        new_env['AGENT_ALIAS_ID'] = agent_alias_id
        
        # Update Lambda configuration
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Environment={
                'Variables': new_env
            }
        )
        
        logger.info(f"Updated Lambda environment variables for {function_name}")
        
        # Wait for the update to complete
        wait_for_lambda_update(function_name)
        
    except Exception as e:
        logger.warning(f"Error updating Lambda environment variables: {e}")
        raise e

def wait_for_lambda_update(function_name, max_attempts=30, delay=10):
    """
    Wait for Lambda update to complete
    """
    for attempt in range(max_attempts):
        try:
            response = lambda_client.get_function(
                FunctionName=function_name
            )
            
            status = response['Configuration']['LastUpdateStatus']
            logger.info(f"Lambda update status: {status} (attempt {attempt+1}/{max_attempts})")
            
            if status == 'Successful':
                return True
            elif status == 'Failed':
                raise Exception(f"Lambda update failed: {response['Configuration'].get('LastUpdateStatusReason', 'Unknown reason')}")
                
            time.sleep(delay)
            
        except Exception as e:
            if 'LastUpdateStatus' not in str(e):
                logger.error(f"Error checking Lambda update status: {e}")
            time.sleep(delay)
    
    raise Exception(f"Timed out waiting for Lambda update to complete after {max_attempts} attempts")
