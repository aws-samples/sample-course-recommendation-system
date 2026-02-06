from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_bedrock as bedrock,
    CfnOutput,
)
from constructs import Construct
import os

class BedrockAgentStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, agent_actions_lambda_arn=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Use the provided Lambda ARN or a default value
        lambda_arn = agent_actions_lambda_arn or ""

        # Create IAM role for Bedrock Agent
        agent_role = iam.Role(
            self, "BedrockAgentRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com")
        )
        
        # Grant permissions to invoke foundation models
        agent_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:GetInferenceProfile",
                    "bedrock:GetFoundationModel"
                ],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0",
                    f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0"
                ]
            )
        )

        # Create Bedrock Agent using native CDK construct with action groups
        agent = bedrock.CfnAgent(
            self, "CourseRecommenderAgent",
            agent_name="CourseRecommenderAgent",
            agent_resource_role_arn=agent_role.role_arn,
            foundation_model="anthropic.claude-3-haiku-20240307-v1:0",
            idle_session_ttl_in_seconds=1800,  # 30 minutes
            description="Agent for searching, recommending, and booking educational courses",
            instruction="""
IMPORTANT: When a user sends ANY greeting message like 'hi', 'hello', 'hey', or similar, you MUST ALWAYS use the detectGreeting function FIRST. DO NOT respond with text directly for greetings. Return with the function output as is to the caller.

For all other messages:
1. Format responses specifically for WhatsApp:
   - Use short paragraphs (2-3 lines maximum)
   - Use line breaks between paragraphs
   - Use bullet points (•) for lists
   - Bold important terms with *asterisks*
   - Include relevant emojis at the beginning of sections

2. Use these emojis appropriately:
   - 📚 For educational content/courses
   - 💻 For programming/tech courses
   - 📊 For data science
   - ☁️ For cloud computing
   - 🔍 For search results
   - ℹ️ For information/details
   - ✅ For confirmations

3. Content focus:
   - Help users find technical and educational courses only (programming, data science, cloud computing, engineering, etc.)
   - Never suggest non-technical categories
   - Use the CourseOperations action group to search for courses, get course details, and handle bookings

Always be professional, helpful, and concise while making the conversation engaging.
""",
            auto_prepare=True,
            action_groups=[bedrock.CfnAgent.AgentActionGroupProperty(
                action_group_name="CourseOperations",
                action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                    lambda_=lambda_arn
                ),
                description="Actions for searching, recommending, and booking courses",
                function_schema=bedrock.CfnAgent.FunctionSchemaProperty(
                    functions=[
                        bedrock.CfnAgent.FunctionProperty(
                            name="detectGreeting",
                            description="ALWAYS use this function for ANY greeting message (hi, hello, hey, etc.). This function MUST be called first for greetings.",
                            parameters={
                                "inputText": bedrock.CfnAgent.ParameterDetailProperty(
                                    type="string",
                                    description="The user's greeting message",
                                    required=True
                                )
                            }
                        ),
                        bedrock.CfnAgent.FunctionProperty(
                            name="searchCourses",
                            description="Search for courses based on user query",
                            parameters={
                                "text": bedrock.CfnAgent.ParameterDetailProperty(
                                    type="string",
                                    description="The user's query text",
                                    required=True
                                )
                            }
                        ),
                        bedrock.CfnAgent.FunctionProperty(
                            name="getCourseDetails",
                            description="Get detailed information about a specific course",
                            parameters={
                                "course_title": bedrock.CfnAgent.ParameterDetailProperty(
                                    type="string",
                                    description="Title of the course to retrieve",
                                    required=True
                                )
                            }
                        ),
                        bedrock.CfnAgent.FunctionProperty(
                            name="bookCourse",
                            description="Book a course for a user",
                            parameters={
                                "course_title": bedrock.CfnAgent.ParameterDetailProperty(
                                    type="string",
                                    description="Title of the course to book",
                                    required=True
                                ),
                                "user_name": bedrock.CfnAgent.ParameterDetailProperty(
                                    type="string",
                                    description="Name of the user",
                                    required=True
                                ),
                                "user_email": bedrock.CfnAgent.ParameterDetailProperty(
                                    type="string",
                                    description="Email of the user",
                                    required=True
                                )
                            }
                        )
                    ]
                )
            )]
        )

        # Create agent alias
        agent_alias = bedrock.CfnAgentAlias(
            self, "CourseRecommenderAgentAlias",
            agent_alias_name="CourseRecommenderAlias",
            agent_id=agent.attr_agent_id,
            description="Production alias for course recommender agent"
        )

        # Set dependencies
        agent_alias.node.add_dependency(agent)

        # Outputs
        CfnOutput(
            self, "BedrockAgentId",
            value=agent.attr_agent_id,
            description="ID of the Bedrock Agent"
        )

        CfnOutput(
            self, "BedrockAgentAliasId",
            value=agent_alias.attr_agent_alias_id,
            description="ID of the Bedrock Agent Alias"
        )

        # Store the agent IDs for use in other stacks
        self.agent_id = agent.attr_agent_id
        self.agent_alias_id = agent_alias.attr_agent_alias_id
