from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_sns_subscriptions as sns_subs,
    aws_glue as glue,
    aws_athena as athena,
    RemovalPolicy,
    Duration,
    CfnOutput
)
from constructs import Construct
import os

class WhatsappAnalyticsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, whatsapp_events_topic=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create a new S3 bucket for WhatsApp messages
        whatsapp_messages_bucket = s3.Bucket(
            self, "WhatsAppMessagesBucket",
            bucket_name=f"whatsapp-eum-messages-{self.region}-{self.account}",
            removal_policy=RemovalPolicy.RETAIN,
            enforce_ssl=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(365)  # Keep messages for 1 year
                )
            ]
        )

        # Create S3 bucket for Athena query results
        athena_results_bucket = s3.Bucket(
            self, "AthenaResultsBucket",
            bucket_name=f"whatsapp-eum-athena-results-{self.region}-{self.account}",
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(30)  # Keep query results for 30 days
                )
            ]
        )

        # Create Lambda function to forward messages to S3
        whatsapp_to_s3_lambda = lambda_.Function(
            self, "WhatsAppToS3Function",
            function_name="whatsapp-course-recommender-to-s3",
            runtime=lambda_.Runtime.PYTHON_3_13,
            code=lambda_.Code.from_asset("lambdas/code/whatsapp_to_s3"),
            handler="lambda_function.lambda_handler",
            environment={
                "BUCKET_NAME": whatsapp_messages_bucket.bucket_name
            },
            timeout=Duration.seconds(30)
        )

        # Grant Lambda permissions to write to S3
        whatsapp_messages_bucket.grant_write(whatsapp_to_s3_lambda)

        # Subscribe Lambda to SNS topic
        if whatsapp_events_topic:
            whatsapp_events_topic.add_subscription(
                sns_subs.LambdaSubscription(whatsapp_to_s3_lambda)
            )

        # Create Glue database
        database_name = "whatsapp_course_recommender_db"
        whatsapp_database = glue.CfnDatabase(
            self, "WhatsAppDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=database_name,
                description="Database for WhatsApp course recommender messages"
            )
        )

        # Create Glue table matching the existing schema
        table_name = "whatsapp_messages"
        whatsapp_table = glue.CfnTable(
            self, "WhatsAppMessagesTable",
            catalog_id=self.account,
            database_name=database_name,
            table_input=glue.CfnTable.TableInputProperty(
                name=table_name,
                description="WhatsApp messages for course recommender",
                storage_descriptor=glue.CfnTable.StorageDescriptorProperty(
                    location=f"s3://{whatsapp_messages_bucket.bucket_name}/",
                    input_format="org.apache.hadoop.mapred.TextInputFormat",
                    output_format="org.apache.hadoop.hive.ql.io.IgnoreKeyTextOutputFormat",
                    serde_info=glue.CfnTable.SerdeInfoProperty(
                        serialization_library="org.openx.data.jsonserde.JsonSerDe"
                    ),
                    columns=[
                        glue.CfnTable.ColumnProperty(name="message_id", type="string"),
                        glue.CfnTable.ColumnProperty(name="event_date", type="string"),
                        glue.CfnTable.ColumnProperty(name="event_time", type="string"),
                        glue.CfnTable.ColumnProperty(name="aws_account_id", type="string"),
                        glue.CfnTable.ColumnProperty(name="status", type="string"),
                        glue.CfnTable.ColumnProperty(name="recipient_id", type="string"),
                        glue.CfnTable.ColumnProperty(name="conversation_id", type="string"),
                        glue.CfnTable.ColumnProperty(name="billable", type="boolean"),
                        glue.CfnTable.ColumnProperty(name="pricing_model", type="string"),
                        glue.CfnTable.ColumnProperty(name="pricing_category", type="string"),
                        glue.CfnTable.ColumnProperty(name="template_name", type="string"),
                        glue.CfnTable.ColumnProperty(name="template_language", type="string")
                    ]
                ),
                partition_keys=[
                    glue.CfnTable.ColumnProperty(name="year", type="int"),
                    glue.CfnTable.ColumnProperty(name="month", type="int"),
                    glue.CfnTable.ColumnProperty(name="day", type="int")
                ],
                table_type="EXTERNAL_TABLE",
                parameters={
                    "classification": "json"
                }
            )
        )
        
        # Set dependency to ensure database is created before table
        whatsapp_table.add_depends_on(whatsapp_database)

        # Create Athena workgroup
        athena_workgroup = athena.CfnWorkGroup(
            self, "WhatsAppAnalyticsWorkgroup",
            name="whatsapp_course_recommender_workgroup",
            description="Workgroup for WhatsApp course recommender analytics",
            recursive_delete_option=True,
            state="ENABLED",
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{athena_results_bucket.bucket_name}/",
                    encryption_configuration=athena.CfnWorkGroup.EncryptionConfigurationProperty(
                        encryption_option="SSE_S3"
                    )
                ),
                publish_cloud_watch_metrics_enabled=True,
                enforce_work_group_configuration=True
            )
        )

        # Output the resources created
        CfnOutput(
            self, "WhatsAppMessagesBucketName",
            value=whatsapp_messages_bucket.bucket_name,
            description="S3 bucket containing WhatsApp messages"
        )
        
        CfnOutput(
            self, "WhatsAppToS3LambdaFunction",
            value=whatsapp_to_s3_lambda.function_name,
            description="Lambda function for WhatsApp analytics"
        )
        
        CfnOutput(
            self, "AthenaQueryUrl",
            value=f"https://{self.region}.console.aws.amazon.com/athena/home?region={self.region}#/query-editor/workgroups/{athena_workgroup.name}",
            description="URL to Athena query editor for WhatsApp analytics"
        )
        
        # Store resources for other stacks to use
        self.whatsapp_messages_bucket = whatsapp_messages_bucket
        self.database_name = database_name
        self.table_name = table_name
