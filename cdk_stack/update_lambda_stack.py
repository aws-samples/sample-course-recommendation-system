from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_iam as iam,
    Duration,
    CustomResource
)
from constructs import Construct

class UpdateLambdaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, whatsapp_forwarder=None, agent_id=None, agent_alias_id=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Create Lambda function for updating Lambda environment variables
        update_lambda_function = lambda_.Function(
            self, "UpdateLambdaFunction",
            runtime=lambda_.Runtime.PYTHON_3_13,
            code=lambda_.Code.from_asset("lambdas/code/update_lambda"),
            handler="index.handler",
            timeout=Duration.seconds(60),
            memory_size=256
        )
        
        # Grant permissions to update Lambda configuration
        update_lambda_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "lambda:GetFunction",
                    "lambda:GetFunctionConfiguration",
                    "lambda:UpdateFunctionConfiguration"
                ],
                resources=[whatsapp_forwarder.function_arn]
            )
        )
        
        # Create custom resource to update Lambda environment variables
        CustomResource(
            self, "UpdateLambdaResource",
            service_token=update_lambda_function.function_arn,
            properties={
                "FunctionName": whatsapp_forwarder.function_name,
                "AgentId": agent_id,
                "AgentAliasId": agent_alias_id
            }
        )
