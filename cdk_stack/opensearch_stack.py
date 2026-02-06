from aws_cdk import (
    Stack,
    aws_opensearchserverless as opensearchserverless,
    CfnOutput,
)
from constructs import Construct

class OpenSearchStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        account_id = Stack.of(self).account

        # Create OpenSearch Serverless Collection
        collection = opensearchserverless.CfnCollection(
            self, "CourseCollection",
            name="course-collection",
            type="SEARCH",
            description="Collection for course data"
        )

        # Create encryption policy
        encryption_policy = opensearchserverless.CfnSecurityPolicy(
            self, "EncryptionPolicy",
            name="course-encryption-policy",
            type="encryption",
            policy="""
            {
                "Rules": [
                    {
                        "ResourceType": "collection",
                        "Resource": [
                            "collection/course-collection"
                        ]
                    }
                ],
                "AWSOwnedKey": true
            }
            """
        )

        # Create network policy - restrict to VPC access only for production
        # Note: For development, you may need to temporarily allow public access
        # and use data access policies to control who can access the collection
        network_policy = opensearchserverless.CfnSecurityPolicy(
            self, "NetworkPolicy",
            name="course-network-policy",
            type="network",
            policy="""
            {
                "Rules": [
                    {
                        "ResourceType": "collection",
                        "Resource": [
                            "collection/course-collection"
                        ]
                    },
                    {
                        "ResourceType": "dashboard",
                        "Resource": [
                            "collection/course-collection"
                        ]
                    }
                ],
                "AllowFromPublic": false
            }
            """
        )

        # Create data access policy - grant access to Lambda execution roles
        # Note: This grants access to the account root. In production, you should
        # replace this with specific Lambda execution role ARNs
        data_access_policy = opensearchserverless.CfnAccessPolicy(
            self, "DataAccessPolicy",
            name="course-data-access-policy",
            type="data",
            policy=f"""
            [
                {{
                    "Rules": [
                        {{
                            "ResourceType": "index",
                            "Resource": [
                                "index/course-collection/*"
                            ],
                            "Permission": [
                                "aoss:CreateIndex",
                                "aoss:DeleteIndex",
                                "aoss:UpdateIndex",
                                "aoss:DescribeIndex",
                                "aoss:ReadDocument",
                                "aoss:WriteDocument"
                            ]
                        }},
                        {{
                            "ResourceType": "collection",
                            "Resource": [
                                "collection/course-collection"
                            ],
                            "Permission": [
                                "aoss:CreateCollectionItems",
                                "aoss:DeleteCollectionItems",
                                "aoss:UpdateCollectionItems",
                                "aoss:DescribeCollectionItems"
                            ]
                        }}
                    ],
                    "Principal": [
                        "arn:aws:iam::{account_id}:root"
                    ]
                }}
            ]
            """
        )

        # Set dependencies
        collection.add_dependency(encryption_policy)
        collection.add_dependency(network_policy)
        collection.add_dependency(data_access_policy)

        # Output the collection endpoint
        CfnOutput(
            self, "CollectionEndpoint",
            value=f"{collection.attr_collection_endpoint}",
            description="OpenSearch Serverless Collection Endpoint"
        )

        # Store the collection endpoint for use in other stacks
        self.collection_endpoint = collection.attr_collection_endpoint
