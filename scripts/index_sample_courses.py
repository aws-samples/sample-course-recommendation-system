#!/usr/bin/env python3
"""
Script to index sample course data into OpenSearch
"""

import json
import argparse
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

# Sample course data
SAMPLE_COURSES = [
    {
        "title": "Introduction to Python Programming",
        "description": "A beginner-friendly course covering Python basics, data structures, and control flow.",
        "level": "beginner",
        "duration": "4 weeks",
        "duration_hours": 32,
        "price": 99.99,
        "instructor": "John Smith",
        "rating": 4.7,
        "keywords": ["python", "programming", "beginner", "coding"]
    },
    {
        "title": "Advanced Machine Learning",
        "description": "Deep dive into neural networks, deep learning, and advanced ML algorithms.",
        "level": "advanced",
        "duration": "8 weeks",
        "duration_hours": 64,
        "price": 299.99,
        "instructor": "Sarah Johnson",
        "rating": 4.9,
        "keywords": ["machine learning", "AI", "deep learning", "neural networks"]
    },
    {
        "title": "Web Development with JavaScript",
        "description": "Learn modern JavaScript frameworks and build responsive web applications.",
        "level": "intermediate",
        "duration": "6 weeks",
        "duration_hours": 48,
        "price": 149.99,
        "instructor": "Michael Brown",
        "rating": 4.5,
        "keywords": ["javascript", "web development", "frontend", "react"]
    },
    {
        "title": "Data Science Fundamentals",
        "description": "Introduction to data analysis, visualization, and basic statistical methods.",
        "level": "beginner",
        "duration": "5 weeks",
        "duration_hours": 40,
        "price": 129.99,
        "instructor": "Emily Chen",
        "rating": 4.6,
        "keywords": ["data science", "statistics", "data analysis", "visualization"]
    },
    {
        "title": "Cloud Architecture on AWS",
        "description": "Design and implement scalable, highly available systems on AWS.",
        "level": "advanced",
        "duration": "6 weeks",
        "duration_hours": 48,
        "price": 249.99,
        "instructor": "David Wilson",
        "rating": 4.8,
        "keywords": ["aws", "cloud", "architecture", "devops"]
    },
    {
        "title": "Mobile App Development with Flutter",
        "description": "Build cross-platform mobile applications using Flutter and Dart.",
        "level": "intermediate",
        "duration": "7 weeks",
        "duration_hours": 56,
        "price": 179.99,
        "instructor": "Lisa Rodriguez",
        "rating": 4.7,
        "keywords": ["flutter", "mobile", "dart", "app development"]
    },
    {
        "title": "Cybersecurity Essentials",
        "description": "Learn fundamental security concepts, threat detection, and protection strategies.",
        "level": "beginner",
        "duration": "4 weeks",
        "duration_hours": 32,
        "price": 149.99,
        "instructor": "Robert Taylor",
        "rating": 4.5,
        "keywords": ["cybersecurity", "security", "hacking", "protection"]
    },
    {
        "title": "DevOps Engineering",
        "description": "Master CI/CD pipelines, containerization, and infrastructure as code.",
        "level": "advanced",
        "duration": "8 weeks",
        "duration_hours": 64,
        "price": 279.99,
        "instructor": "Jennifer Adams",
        "rating": 4.8,
        "keywords": ["devops", "docker", "kubernetes", "ci/cd"]
    },
    {
        "title": "Digital Marketing Fundamentals",
        "description": "Learn SEO, social media marketing, and digital advertising strategies.",
        "level": "beginner",
        "duration": "5 weeks",
        "duration_hours": 40,
        "price": 119.99,
        "instructor": "Thomas Green",
        "rating": 4.4,
        "keywords": ["marketing", "digital", "seo", "social media"]
    },
    {
        "title": "Blockchain Development",
        "description": "Build decentralized applications and smart contracts on Ethereum.",
        "level": "intermediate",
        "duration": "7 weeks",
        "duration_hours": 56,
        "price": 199.99,
        "instructor": "Alex Martinez",
        "rating": 4.6,
        "keywords": ["blockchain", "ethereum", "smart contracts", "web3"]
    }
]

def create_index(client, index_name):
    """Create an index with the appropriate mapping"""
    index_body = {
        "settings": {
            "index": {
                "number_of_shards": 4,
                "number_of_replicas": 1
            }
        },
        "mappings": {
            "properties": {
                "title": {"type": "text"},
                "description": {"type": "text"},
                "level": {"type": "keyword"},
                "duration": {"type": "text"},
                "duration_hours": {"type": "integer"},
                "price": {"type": "float"},
                "instructor": {"type": "text"},
                "rating": {"type": "float"},
                "keywords": {"type": "keyword"}
            }
        }
    }
    
    try:
        response = client.indices.create(index=index_name, body=index_body)
        print(f"Created index: {index_name}")
        print(response)
    except Exception as e:
        if "resource_already_exists_exception" in str(e):
            print(f"Index {index_name} already exists")
        else:
            print(f"Error creating index: {e}")
            raise

def index_courses(client, index_name, courses):
    """Index the sample courses"""
    for i, course in enumerate(courses):
        try:
            response = client.index(
                index=index_name,
                id=str(i+1),
                body=course,
                refresh=True
            )
            print(f"Indexed course: {course['title']}")
        except Exception as e:
            print(f"Error indexing course {course['title']}: {e}")

def main():
    parser = argparse.ArgumentParser(description='Index sample courses into OpenSearch')
    parser.add_argument('--endpoint', required=True, help='OpenSearch endpoint')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--index', default='courses', help='Index name')
    
    args = parser.parse_args()
    
    # Create AWS auth
    session = boto3.Session()
    credentials = session.get_credentials()
    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        args.region,
        'aoss',
        session_token=credentials.token
    )
    
    # Create OpenSearch client
    client = OpenSearch(
        hosts=[{'host': args.endpoint, 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    
    # Create index and index courses
    create_index(client, args.index)
    index_courses(client, args.index, SAMPLE_COURSES)
    
    print(f"Successfully indexed {len(SAMPLE_COURSES)} courses")

if __name__ == "__main__":
    main()
