import json
import os
import boto3
import logging
from botocore.config import Config

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Bedrock Agent Runtime client with retry configuration
retry_config = Config(
    retries={
        'max_attempts': 10,
        'mode': 'adaptive'
    }
)

bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', config=retry_config)

def lambda_handler(event, context):
    """
    Lambda handler for WhatsApp messages from AWS End User Messaging
    This function forwards messages to the Bedrock Agent and sends responses back
    """
    try:
        # Process SNS messages
        for record in event.get('Records', []):
            try:
                # Parse SNS message
                sns_message = json.loads(record['Sns']['Message'])

                # Parse the whatsAppWebhookEntry string into a JSON object
                webhook_entry = json.loads(sns_message.get('whatsAppWebhookEntry', '{}'))
                
                # Extract metadata from context
                context = sns_message.get('context', {})
                phone_number_ids = context.get('MetaPhoneNumberIds', [{}])[0] if context.get('MetaPhoneNumberIds') else {}
                
                metadata = {
                    'originationNumber': phone_number_ids.get('metaPhoneNumberId', ''),
                    'originationNumberArn': phone_number_ids.get('arn', '')
                }
                
                # Extract messages from webhook entry
                changes = webhook_entry.get('changes', [{}])[0]
                value = changes.get('value', {})
                
                if 'messages' in value:
                    for msg in value.get('messages', []):
                        process_message(msg, metadata)
                
            except Exception as e:
                logger.error(f"Error processing record: {e}", exc_info=True)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Message processed successfully')
        }
        
    except Exception as e:
        logger.error(f"Error in lambda handler: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }

def process_message(message, metadata):
    """
    Process a WhatsApp message by forwarding it to the Bedrock Agent
    """
    try:
        message_id = message.get('id')
        message_type = message.get('type')
        phone_number = message.get('from')  # Extract phone number directly from message
        
        if not phone_number:
            logger.error("No phone number found in message")
            return
        
        # Extract message text based on type
        message_text = ""
        if message_type == 'text':
            message_text = message.get('text', {}).get('body', '')
        elif message_type == 'button':
            message_text = message.get('button', {}).get('payload', '')
        elif message_type == 'interactive':
            interactive = message.get('interactive', {})
            interactive_type = interactive.get('type')
            
            if interactive_type == 'button_reply':
                message_text = f"Button: {interactive.get('button_reply', {}).get('title', '')}"
            elif interactive_type == 'list_reply':
                message_text = f"List selection: {interactive.get('list_reply', {}).get('title', '')}"
        else:
            message_text = f"[Received {message_type} message]"
        
        if not message_text:
            logger.error("No message text extracted")
            return
        
        # Get agent IDs from environment variables
        agent_id = os.environ.get('AGENT_ID')
        agent_alias_id = os.environ.get('AGENT_ALIAS_ID')
        
        if not agent_id or not agent_alias_id:
            logger.error("Agent ID or Agent Alias ID not configured")
            send_whatsapp_reply(
                message_id, 
                phone_number, 
                "Sorry, the system is not properly configured. Please try again later.", 
                metadata
            )
            return
        
        # Forward message to Bedrock Agent
        logger.info(f"Forwarding message to Bedrock Agent: {message_text}")
        
        response = bedrock_agent_runtime.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=phone_number,  # Use phone number as session ID
            inputText=message_text,
            enableTrace=True  # Enable tracing
        )
        
        # Process agent response
        completion = ""
        trace_data = None
        
        for event in response.get("completion"):
            if "chunk" in event:
                chunk = event["chunk"]
                completion = completion + chunk["bytes"].decode()
            
            # Check for trace data
            if "trace" in event:
                trace_data = event["trace"]
        
        logger.info(f"Agent response: {completion}")
        
        # Log trace data if available
        if trace_data:
            logger.info(f"Agent trace: {str(trace_data)}")
        
        # Try to parse the response as JSON
        try:
            response_data = json.loads(completion)
            if isinstance(response_data, dict):
                # Check if it's a function response with custom format
                try:
                    if response_data.get('messageFormat') == 'custom':
                        # Check if it's a carousel response
                        if response_data.get('responseType') == 'carousel':
                            send_carousel_template(message_id, phone_number, metadata)
                            return
                except Exception as e:
                    logging.error("Exception parsing response_data {} {}", response_data, e)
        except:
            # Not JSON or not a custom response, continue with normal flow
            logging.info("Not a custom response, continuing with normal flow")
        
        # Send response back to user
        send_whatsapp_reply(message_id, phone_number, completion, metadata)
        
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        # Try to send error message to user
        try:
            send_whatsapp_reply(
                message_id, 
                phone_number, 
                "Sorry, I encountered an error processing your message. Please try again later.", 
                metadata
            )
        except:
            logger.error("Failed to send error message to user")

def send_carousel_template(message_id, phone_number, metadata):
    """Send WhatsApp carousel template for course catalog"""
    try:
        client = boto3.client('socialmessaging', region_name='ap-south-1')
        
        carousel_template = {
                "messaging_product": "whatsapp",
                "to": f"+{phone_number}",
                "type": "template",
                "template": {
                    "name": "course_catalog_v10",
                    "language": {
                        "code": "en"
                    },
                    "components": [{
                            "type": "body",
                            "parameters": [{
                                    "type": "text",
                                    "text": "Cloud Computing"
                                },
                                {
                                    "type": "text",
                                    "text": "Machine Learning"
                                },
                                {
                                    "type": "text",
                                    "text": "Data Science"
                                }
                            ]
                        },
                        {
                            "type": "carousel",
                            "cards": [{
                                    "card_index": 0,
                                    "components": [{
                                            "type": "header",
                                            "parameters": [{
                                                "type": "image",
                                                "image": {
                                                    "id": "1068347741892049"
                                                }
                                            }]
                                        },
                                        {
                                            "type": "body",
                                            "parameters": [{
                                                "type": "text",
                                                "text": "Programming"
                                            }]
                                        },
                                        {
                                            "type": "button",
                                            "sub_type": "quick_reply",
                                            "index": "0",
                                            "parameters": [{
                                                "type": "text",
                                                "text": "Show me some Programming courses"
                                            }]
                                        }
                                    ]
                                },
                                {
                                    "card_index": 1,
                                    "components": [{
                                            "type": "header",
                                            "parameters": [{
                                                "type": "image",
                                                "image": {
                                                    "id": "704959258834752"
                                                }
                                            }]
                                        },
                                        {
                                            "type": "body",
                                            "parameters": [{
                                                "type": "text",
                                                "text": "Cloud Computing"
                                            }]
                                        },
                                        {
                                            "type": "button",
                                            "sub_type": "quick_reply",
                                            "index": "0",
                                            "parameters": [{
                                                "type": "text",
                                                "text": "Show me some Cloud Computing courses"
                                            }]
                                        }
                                    ]

                                },
                                {
                                    "card_index": 2,
                                    "components": [{
                                            "type": "header",
                                            "parameters": [{
                                                "type": "image",
                                                "image": {
                                                    "id": "1282410307004034"
                                                }
                                            }]
                                        },
                                        {
                                            "type": "body",
                                            "parameters": [{
                                                "type": "text",
                                                "text": "Data Science"
                                            }]
                                        },
                                        {
                                            "type": "button",
                                            "sub_type": "quick_reply",
                                            "index": "0",
                                            "parameters": [{
                                                "type": "text",
                                                "text": "Show me some Data Science courses"
                                            }]
                                        }
                                    ]

                                },
                                {
                                    "card_index": 3,
                                    "components": [{
                                            "type": "header",
                                            "parameters": [{
                                                "type": "image",
                                                "image": {
                                                    "id": "722423164071961"
                                                }
                                            }]
                                        },
                                        {
                                            "type": "body",
                                            "parameters": [{
                                                "type": "text",
                                                "text": "Machine Learning"
                                            }]
                                        },
                                        {
                                            "type": "button",
                                            "sub_type": "quick_reply",
                                            "index": "0",
                                            "parameters": [{
                                                "type": "text",
                                                "text": "Show me some Machine Learning courses"
                                            }]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            }
        
        client.send_whatsapp_message(
            originationPhoneNumberId=metadata.get('originationNumberArn'),
            metaApiVersion="v20.0",
            message=bytes(json.dumps(carousel_template), "utf-8")
        )

    except Exception as e:
        logger.error(f"Error sending carousel template: {e}")

def send_whatsapp_reply(message_id, phone_number, text, metadata):
    """Send a WhatsApp reply"""
    try:
        client = boto3.client('socialmessaging', region_name='ap-south-1')
        
        message_object = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "context": {"message_id": message_id},
            "to": f"+{phone_number}",
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        
        client.send_whatsapp_message(
            originationPhoneNumberId=metadata.get('originationNumberArn'),
            metaApiVersion="v20.0",
            message=bytes(json.dumps(message_object), "utf-8")
        )

    except Exception as e:
        logger.error(f"Error sending WhatsApp reply: {e}")
