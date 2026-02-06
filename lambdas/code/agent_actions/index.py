import json
import boto3
import logging
from datetime import datetime
from opensearch_utils import search_courses as semantic_search_courses, retry_with_backoff, init_opensearch

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
bedrock = boto3.client('bedrock-runtime')


def lambda_handler(event, context):
    """
    Handler for Bedrock Agent action group invocations
    """
    
    try:
        # Extract function name from the event (now at top level)
        function_name = event.get('function', 'searchCourses')
        
        # Extract input text directly from inputText field
        input_text = event.get('inputText', '')
        
        # Extract parameters from the list format
        parameters = {}
        if 'parameters' in event and isinstance(event['parameters'], list):
            for param in event['parameters']:
                if isinstance(param, dict) and 'name' in param and 'value' in param:
                    parameters[param['name']] = param['value']
        
        # Initialize services
        if not init_opensearch():
            return format_response({
                "error": "OpenSearch service is not available"
            }, 500, function_name)
        
        # Process based on function name
        if function_name == 'searchCourses':
            # If we have a text parameter, use it, otherwise use inputText
            query_text = parameters.get('text', input_text)
            
            # Extract subject from input text using Bedrock
            subject = extract_subject(query_text)
            
            # Extract optional parameters
            level = extract_parameter(query_text, "level")
            duration = extract_parameter(query_text, "duration")
            price_range = extract_parameter(query_text, "price_range")
            
            # Build request body
            request_body = {
                "subject": subject,
                "page": 1,
                "page_size": 10
            }
            
            # Add optional parameters if available
            if level:
                request_body["level"] = level
            if duration:
                request_body["duration"] = duration
            if price_range:
                request_body["price_range"] = price_range
            
            # Search for courses
            result = search_courses(request_body)
            return format_response(result, 200, function_name)
        elif function_name == 'getCourseDetails':
            course_title = parameters.get('course_title', '')
            result = get_course_details({"course_title": course_title})
            return format_response(result, 200, function_name)
        elif function_name == 'detectGreeting':
            input_text = parameters.get('inputText', '')
            result = handle_greeting()
            return format_response(result, 200, function_name)
        elif function_name == 'bookCourse':
            result = book_course({
                "course_title": parameters.get('course_title', ''),
                "user_name": parameters.get('user_name', ''),
                "user_email": parameters.get('user_email', '')
            })
            return format_response(result, 200, function_name)
        else:
            return format_response({
                "error": f"Unsupported function: {function_name}"
            }, 400, function_name)
            
    except Exception as e:
        logger.error(f"Error processing action: {e}", exc_info=True)
        return format_response({
            "error": str(e)
        }, 500, function_name if 'function_name' in locals() else "error")

def extract_subject(input_text):
    """
    Extract subject from input text using Bedrock with retry
    """
    prompt = f"""
    <instruction>
    Extract the main subject or topic the user is interested in learning from the following text:
    "{input_text}"
    
    Return ONLY the subject or topic as a single word or short phrase, nothing else.
    </instruction>
    """
    
    def _extract_subject():
        response = bedrock.converse(
            modelId='apac.anthropic.claude-3-haiku-20240307-v1:0',
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={
                "maxTokens": 128,
                "temperature": 0.1
            }
        )
        return response["output"]["message"]["content"][0]["text"].strip()
    
    try:
        return retry_with_backoff(_extract_subject)
    except Exception as e:
        logger.error(f"Error extracting subject after retries: {e}")
        # Return a default or partial match if extraction fails
        words = input_text.split()
        return words[0] if words else "general"

def extract_parameter(input_text, param_type):
    """
    Extract optional parameters from input text using Bedrock with retry
    """
    param_descriptions = {
        "level": "difficulty level (beginner, intermediate, or expert)",
        "duration": "course duration (e.g., '4 weeks', '2 months')",
        "price_range": "price range or budget (e.g., 'under $100', 'free')"
    }
    
    prompt = f"""
    <instruction>
    Extract the {param_descriptions[param_type]} from the following text:
    "{input_text}"
    
    If the {param_descriptions[param_type]} is mentioned, return ONLY that value as a short phrase.
    If not mentioned, return "NONE".
    </instruction>
    """
    
    def _extract_parameter():
        response = bedrock.converse(
            modelId='apac.anthropic.claude-3-haiku-20240307-v1:0',
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={
                "maxTokens": 128,
                "temperature": 0.1
            }
        )
        return response["output"]["message"]["content"][0]["text"].strip()
    
    try:
        value = retry_with_backoff(_extract_parameter)
        return value if value != "NONE" else None
    except Exception as e:
        logger.error(f"Error extracting {param_type} after retries: {e}")
        return None

def search_courses(request_body):
    """
    Search for courses based on criteria
    """
    # Extract search parameters
    subject = request_body.get('subject', '')
    level = request_body.get('level')
    page = request_body.get('page', 1)
    page_size = request_body.get('page_size', 10)
    
    # Build filters
    filters = []
    
    # Add level filter if specified
    if level:
        filters.append({
            "term": {
                "difficultyLevel": level
            }
        })
    
    try:
        courses = semantic_search_courses(subject, filters)
        total_results = len(courses)
        total_pages = (total_results + page_size - 1) // page_size
        
        # Apply pagination manually
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_courses = courses[start_idx:end_idx]
        
        # Return results in the original format from OpenSearch
        return {
            "courses": paginated_courses,
            "totalResults": total_results,
            "currentPage": page,
            "totalPages": total_pages
        }
    except Exception as e:
        logger.error(f"Semantic search error: {e}")
                

def get_course_details(request_body):
    """
    Get detailed information about a specific course by title using OpenSearch
    """
    try:
        course_title = request_body.get('course_title', '')
        
        if not course_title:
            return {
                'success': False,
                'message': "Course title is required"
            }
        
        # Execute search
        try:
            response = semantic_search_courses(course_title)
        except Exception as e:
            logger.error(f"OpenSearch query error: {e}")
            return {
                'success': False,
                'message': f"Error searching for course: {str(e)}"
            }
        
        if not response:
            return {
                'success': False,
                'message': f"Course with title '{course_title}' not found"
            }
        
        # Get the best matching course
        course = response[0]
        
        return {
            'course': course,
            'success': True
        }
        
    except Exception as e:
        logger.error(f"Error getting course details: {e}", exc_info=True)
        return {
            'success': False,
            'message': f"Error getting course details: {str(e)}"
        }

def handle_greeting():
    """
    Handle greeting messages and return carousel response with technical course categories
    """
    return {
        "messageFormat": "custom",
        "responseType": "carousel",
        "message": "Welcome to our technical course recommender! Here are popular technical categories to explore."
    }

def book_course(request_body):
    """
    Book a course for a user by course title
    """
    try:
        # Extract booking details
        course_title = request_body.get('course_title')
        user_name = request_body.get('user_name')
        user_email = request_body.get('user_email')
        
        # Generate booking ID
        booking_id = f"BK-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # In a real implementation, this would save to a database
        # For this example, we just return a success response        
        return {
            'booking_id': booking_id,
            'course_title': course_title,
            'user_name': user_name,
            'user_email': user_email,
            'start_date': datetime.now().strftime('%Y-%m-%d'),
            'status': 'CONFIRMED',
            'message': f'Successfully booked "{course_title}"',
            'success': True
        }
        
    except Exception as e:
        logger.error(f"Error booking course: {e}", exc_info=True)
        return {
            'success': False,
            'message': f"Error booking course: {str(e)}"
        }

def format_response(body, status_code=200, function_name=None):
    """
    Format response according to Bedrock Agent requirements for function invocation
    """
    # Convert body to string if it's not already
    body_str = json.dumps(body) if isinstance(body, (dict, list)) else str(body)
    
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": "CourseOperations",
            "function": function_name,
            "functionResponse": {
                "responseBody": {
                    "TEXT": {
                        "body": body_str
                    }
                }
            }
        },
        "sessionAttributes": {},
        "promptSessionAttributes": {}
    }
