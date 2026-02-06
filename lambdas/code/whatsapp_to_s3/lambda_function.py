import json
import boto3
from datetime import datetime
import uuid
import os

def process_webhook_entry(webhook_entry):
    """Helper function to process webhook entry and extract status information"""
    processed_data = {}
    
    if 'changes' in webhook_entry:
        for change in webhook_entry['changes']:
            if change.get('field') == 'messages' and 'value' in change:
                if 'statuses' in change['value']:
                    status = change['value']['statuses'][0]
                    processed_data.update({
                        'status': status.get('status', ''),
                        'recipient_id': status.get('recipient_id', ''),
                        'conversation_id': status.get('conversation', {}).get('id', ''),
                        'billable': status.get('pricing', {}).get('billable', False),
                        'pricing_model': status.get('pricing', {}).get('pricing_model', ''),
                        'pricing_category': status.get('pricing', {}).get('category', ''),
                        'template_name': None,
                        'template_language': None
                    })
            elif change.get('field') == 'message_template_status_update':
                processed_data.update({
                    'status': 'TEMPLATE_' + change['value'].get('event', ''),
                    'template_name': change['value'].get('message_template_name', ''),
                    'template_language': change['value'].get('message_template_language', ''),
                    'recipient_id': None,
                    'conversation_id': None,
                    'billable': False,
                    'pricing_model': None,
                    'pricing_category': None
                })
    return processed_data

def lambda_handler(event, context):
    s3_client = boto3.client('s3')
    bucket_name = os.environ.get('BUCKET_NAME')
    
    try:
        for record in event['Records']:
            # Get the SNS message
            sns_message = record['Sns']
            message_data = json.loads(sns_message['Message'])
            
            # Extract webhook entry
            webhook_entry = json.loads(message_data['whatsAppWebhookEntry'])
            
            # Parse timestamp
            dt = datetime.strptime(sns_message['Timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
            
            # Process the base message with formatted dates
            processed_data = {
                'message_id': sns_message['MessageId'],
                'event_date': dt.strftime('%Y-%m-%d'),  # Date in YYYY-MM-DD format
                'event_time': dt.strftime('%H:%M:%S'),  # Time in HH:MM:SS format
                'aws_account_id': message_data['aws_account_id']
            }
            
            # Process webhook entry and update processed_data
            webhook_data = process_webhook_entry(webhook_entry)
            processed_data.update(webhook_data)
            
            # Generate file name with date partition
            file_name = f"year={dt.year}/month={dt.month:02d}/day={dt.day:02d}/{str(uuid.uuid4())}.json"
            
            # Store in S3
            s3_client.put_object(
                Bucket=bucket_name,
                Key=file_name,
                Body=json.dumps(processed_data),
                ContentType='application/json'
            )
            
            print(f"Successfully processed message: {processed_data['message_id']}")
            
    except Exception as e:
        print(f"Error processing message: {str(e)}")
        raise e
    
    return {
        'statusCode': 200,
        'body': json.dumps('Messages processed successfully')
    }
