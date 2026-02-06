import json
import boto3
import os
import logging
import time
import random
from botocore.exceptions import ClientError
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize OpenSearch client
opensearch_client = None

def retry_with_backoff(func, max_retries=5, initial_backoff=1, max_backoff=32):
    """
    Retry a function with exponential backoff
    
    Args:
        func: The function to retry
        max_retries: Maximum number of retries
        initial_backoff: Initial backoff time in seconds
        max_backoff: Maximum backoff time in seconds
        
    Returns:
        The result of the function call
    """
    retries = 0
    backoff = initial_backoff
    
    while True:
        try:
            return func()
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            error_message = e.response.get('Error', {}).get('Message', '')
            
            # Check if this is a throttling error
            if (error_code in ['ThrottlingException', 'TooManyRequestsException', 'RequestLimitExceeded'] or
                'request rate is too high' in error_message.lower() or
                'throttling' in error_message.lower()):
                
                # If we've reached max retries, raise the exception
                if retries >= max_retries:
                    logger.error(f"Maximum retries ({max_retries}) reached. Last error: {e}")
                    raise e
                
                # Calculate backoff time with jitter
                sleep_time = min(backoff + random.uniform(0, 1), max_backoff)
                logger.info(f"Request rate too high. Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
                
                # Increase backoff for next retry
                retries += 1
                backoff = min(backoff * 2, max_backoff)
            else:
                # If it's not a throttling error, raise it immediately
                raise e
        except Exception as e:
            # For non-ClientError exceptions, check if it's a rate limit error
            error_message = str(e).lower()
            if ('request rate is too high' in error_message or
                'throttling' in error_message or
                'too many requests' in error_message):
                
                # If we've reached max retries, raise the exception
                if retries >= max_retries:
                    logger.warning(f"Maximum retries ({max_retries}) reached. Last error: {e}")
                    raise e
                
                # Calculate backoff time with jitter
                sleep_time = min(backoff + random.uniform(0, 1), max_backoff)
                logger.info(f"Request rate too high. Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
                
                # Increase backoff for next retry
                retries += 1
                backoff = min(backoff * 2, max_backoff)
            else:
                # If it's not a throttling error, raise it immediately
                raise e

def get_embedding(text):
    """Generate embeddings for text using Amazon Bedrock's Titan Embed model with retry"""
    def _get_embedding():
        bedrock = boto3.client('bedrock-runtime')
        response = bedrock.invoke_model(
            modelId='amazon.titan-embed-text-v2:0',
            body=json.dumps({
                "inputText": text
            })
        )
        response_body = json.loads(response.get('body').read())
        return response_body['embedding']
    
    try:
        return retry_with_backoff(_get_embedding)
    except Exception as e:
        logger.warning(f"Error generating embedding after retries: {str(e)}")
        raise e

def init_opensearch():
    """Initialize connection to OpenSearch"""
    credentials = boto3.Session().get_credentials()
    region = os.environ.get('AWS_REGION', 'us-east-1')
    auth = AWSV4SignerAuth(credentials, region, 'aoss')
    
    opensearch_client = OpenSearch(
        hosts=[{'host': os.environ.get('OPENSEARCH_ENDPOINT'), 'port': 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=300
    )
    return opensearch_client

def semantic_search(query_text, filters=None, k=10):
    """Perform semantic search using vector embeddings"""
    opensearch = init_opensearch()
    query_embedding = get_embedding(query_text)
    
    search_query = {
        "_source": {
            "excludes": ["content_vector"]
        },
        "query": {
            "bool": {
                "must": [
                    {
                        "knn": {
                            "content_vector": {
                                "vector": query_embedding,
                                "k": k
                            }
                        }
                    }
                ]
            }
        }
    }
    
    # Add filters if provided
    if filters:
        search_query["query"]["bool"]["filter"] = filters
    
    def _search():
        return opensearch.search(
            index=os.environ.get('OPENSEARCH_INDEX', 'courses'),
            body=search_query
        )
    
    try:
        results = retry_with_backoff(_search)
        return results['hits']['hits']
    except Exception as e:
        logger.warning(f"Error in semantic search after retries: {str(e)}")
        raise e

def search_courses(query, filters=None):
    """Search courses using semantic search"""
    try:
        results = semantic_search(query, filters)
        
        # Format results
        formatted_results = []
        for hit in results:
            course = hit["_source"]
            # Add score and ID to the course
            course["score"] = hit["_score"]
            if "courseId" not in course and "_id" in hit:
                course["courseId"] = hit["_id"]
            formatted_results.append(course)
        
        return formatted_results
    except Exception as e:
        logger.error(f"Error searching courses: {str(e)}")
        return []
