from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_dynamodb as dynamodb,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subs,
    aws_iam as iam,
    aws_s3 as s3,
    Duration,
    CfnOutput,
    BundlingOptions,
    DockerImage,
    CfnParameter
)
from constructs import Construct
import os

class WhatsappCourseRecommenderStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Parameters
        opensearch_endpoint = CfnParameter(
            self, "OpenSearchEndpoint",
            type="String",
            description="OpenSearch Serverless Collection Endpoint (leave empty to create a new one)",
            default=""
        )
        
        whatsapp_origination_number = CfnParameter(
            self, "WhatsAppOriginationNumber",
            type="String",
            description="WhatsApp Origination Number ID",
            default="<phone-number-id-eum>"
        )

        # Create SNS topic for WhatsApp events
        whatsapp_events_topic = sns.Topic(
            self, "WhatsAppEventsTopic",
            display_name="WhatsApp Events Topic",
            enforce_ssl=True
        )
        
        # Create Lambda layer for OpenSearch
        opensearch_layer = lambda_.LayerVersion(
            self, "OpenSearchLayer",
            code=lambda_.Code.from_asset(
                path="lambdas/layers/opensearch",
                bundling=BundlingOptions(
                    image=DockerImage.from_registry("public.ecr.aws/sam/build-python3.9"),
                    command=[
                        "bash", "-c",
                        "pip install opensearch-py requests-aws4auth -t /asset-output/python && " +
                        "cp -au /asset-output/python /tmp/python"
                    ],
                    user="root"
                )
            ),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_13],
            description="OpenSearch Python library"
        )
        
        # Create boto3 layer
        boto3_layer = lambda_.LayerVersion(
            self, "Boto3Layer",
            code=lambda_.Code.from_asset(
                path="lambdas/layers/boto3",
                bundling=BundlingOptions(
                    image=DockerImage.from_registry("public.ecr.aws/sam/build-python3.9"),
                    command=[
                        "bash", "-c",
                        "pip install boto3 -t /asset-output/python && " +
                        "cp -au /asset-output/python /tmp/python"
                    ],
                    user="root"
                )
            ),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_13],
            description="Boto3 Python library"
        )
        
        # Create agent actions Lambda
        agent_actions = lambda_.Function(
            self, "AgentActionsFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            code=lambda_.Code.from_asset("lambdas/code/agent_actions"),
            handler="index.lambda_handler",
            timeout=Duration.seconds(300),
            memory_size=256,
            function_name="course-recommender-agent-actions",
            environment={
                "OPENSEARCH_ENDPOINT": opensearch_endpoint.value_as_string,
                "OPENSEARCH_INDEX": "courses",
                "WHATSAPP_ORIGINATION_NUMBER": whatsapp_origination_number.value_as_string
            },
            layers=[opensearch_layer]
        )
        
        # Add permission for Bedrock to invoke the Lambda function
        agent_actions.add_permission(
            "BedrockInvoke",
            principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
            action="lambda:InvokeFunction"
        )
        
        # Create WhatsApp forwarder Lambda
        whatsapp_forwarder = lambda_.Function(
            self, "WhatsAppForwarderFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            code=lambda_.Code.from_asset("lambdas/code/whatsapp_forwarder"),
            handler="lambda_function.lambda_handler",
            timeout=Duration.seconds(30),
            memory_size=256,
            function_name="whatsapp-forwarder",
            environment={
                "AGENT_ID": "",  # Will be updated after agent creation
                "AGENT_ALIAS_ID": ""  # Will be updated after agent creation
            },
            layers=[boto3_layer],
        )
        
        # Grant permissions for agent actions
        agent_actions.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "socialmessaging:SendWhatsAppMessage",
                    "socialmessaging:GetWhatsAppMessageMedia"
                ],
                resources=["*"]
            )
        )
        
        agent_actions.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "aoss:APIAccessAll"
                ],
                resources=["*"]
            )
        )
        
        # Add Bedrock permissions for vector embeddings
        agent_actions.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel"
                ],
                resources=["*"]
            )
        )
        
        # Grant permissions for WhatsApp forwarder
        whatsapp_forwarder.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "social-messaging:SendWhatsAppMessage",
                    "social-messaging:GetWhatsAppMessageMedia"
                ],
                resources=["*"]
            )
        )
        
        whatsapp_forwarder.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeAgent"
                ],
                resources=["*"]
            )
        )
        
        
        # Subscribe WhatsApp forwarder to SNS topic
        whatsapp_events_topic.add_subscription(
            sns_subs.LambdaSubscription(whatsapp_forwarder)
        )
        
        # Outputs
        CfnOutput(
            self, "SNSTopicArn",
            value=whatsapp_events_topic.topic_arn,
            description="ARN of the SNS topic for WhatsApp events"
        )
        
        CfnOutput(
            self, "WhatsAppForwarderFunctionName",
            value=whatsapp_forwarder.function_name,
            description="Name of the WhatsApp forwarder Lambda function"
        )
        
        CfnOutput(
            self, "AgentActionsFunctionName",
            value=agent_actions.function_name,
            description="Name of the agent actions Lambda function"
        )
        
        CfnOutput(
            self, "AgentActionsLambdaArn",
            value=agent_actions.function_arn,
            description="ARN of the agent actions Lambda function"
        )
        
        # Store the Lambda ARN for use in other stacks
        self.agent_actions_lambda_arn = agent_actions.function_arn
        self.whatsapp_forwarder = whatsapp_forwarder
        self.whatsapp_events_topic = whatsapp_events_topic
