#!/usr/bin/env python3
import os
import aws_cdk as cdk
from cdk_stack.whatsapp_course_recommender_stack import WhatsappCourseRecommenderStack
from cdk_stack.analytics_stack import WhatsappAnalyticsStack
from cdk_stack.opensearch_stack import OpenSearchStack
from cdk_stack.bedrock_agent_stack import BedrockAgentStack
from cdk_stack.quicksight_stack import QuickSightDashboardStack
from cdk_stack.update_lambda_stack import UpdateLambdaStack



app = cdk.App()

# Environment
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1")
)

# Check if OpenSearchEndpoint parameter is provided
opensearch_endpoint_param = app.node.try_get_context("opensearch_endpoint")
deploy_opensearch = opensearch_endpoint_param is None or opensearch_endpoint_param == ""

# Deploy OpenSearch stack only if no endpoint is provided
opensearch_stack = None
if deploy_opensearch:
    opensearch_stack = OpenSearchStack(app, "WhatsappCourseRecommenderOpenSearchStack", env=env)

# Deploy main stack with Lambda functions
main_stack = WhatsappCourseRecommenderStack(app, "WhatsappCourseRecommenderStack", env=env)

# Add dependency to OpenSearch stack if it was deployed
if deploy_opensearch and opensearch_stack:
    main_stack.add_dependency(opensearch_stack)

# Get the agent actions Lambda ARN from the main stack
agent_actions_lambda_arn = main_stack.agent_actions_lambda_arn

# Deploy Bedrock Agent stack with Lambda ARN from main stack
bedrock_agent_stack = BedrockAgentStack(
    app, 
    "WhatsappCourseRecommenderAgentStack",
    agent_actions_lambda_arn=agent_actions_lambda_arn,
    env=env
)
bedrock_agent_stack.node.add_dependency(main_stack)

# Deploy update Lambda stack to update WhatsApp forwarder with agent IDs
update_lambda_stack = UpdateLambdaStack(
    app,
    "WhatsappCourseRecomUpdateLambdaStack",
    whatsapp_forwarder=main_stack.whatsapp_forwarder,
    agent_id=bedrock_agent_stack.agent_id,
    agent_alias_id=bedrock_agent_stack.agent_alias_id,
    env=env
)
update_lambda_stack.node.add_dependency(bedrock_agent_stack)

analytics_stack = WhatsappAnalyticsStack(
    app, 
    "WhatsappCourseRecommenderAnalyticsStack",
    whatsapp_events_topic=main_stack.whatsapp_events_topic,
    env=env
)

analytics_stack.add_dependency(main_stack)

quicksight_dashboard_stack = QuickSightDashboardStack(
    app, 
    "WhatsappCourseRecommenderQuickSightStack",
    analytics_stack=analytics_stack,
    env=env
)
quicksight_dashboard_stack.add_dependency(analytics_stack)

app.synth()
