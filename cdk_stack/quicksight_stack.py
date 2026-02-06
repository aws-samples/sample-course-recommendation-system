from aws_cdk import (
    Stack,
    aws_quicksight as quicksight,
    CfnOutput,
    CfnParameter
)
from constructs import Construct

class QuickSightDashboardStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, analytics_stack=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get references from the analytics stack
        database_name = analytics_stack.database_name
        table_name = analytics_stack.table_name
        
        # QuickSight AWS account ID - this is your AWS account ID
        quicksight_account_id = self.account
        
        # Create a CloudFormation parameter for QuickSight username
        quicksight_username_param = CfnParameter(
            self, "QuickSightUsername",
            type="String",
            description="QuickSight username that will own the resources",
            default="Admin"  # Default value if not provided
        )
        
        # Get the username from the parameter
        quicksight_username = quicksight_username_param.value_as_string

        
        # Create a QuickSight data source for Athena
        data_source = quicksight.CfnDataSource(
            self, "WhatsAppAnalyticsDataSource",
            aws_account_id=quicksight_account_id,
            data_source_id="whatsapp-analytics-source",
            name="WhatsApp Analytics",
            type="ATHENA",
            data_source_parameters=quicksight.CfnDataSource.DataSourceParametersProperty(
                athena_parameters=quicksight.CfnDataSource.AthenaParametersProperty(
                    work_group="whatsapp_course_recommender_workgroup"
                )
            )
        )
        
        # Create a QuickSight dataset
        dataset = quicksight.CfnDataSet(
            self, "WhatsAppAnalyticsDataSet",
            aws_account_id=quicksight_account_id,
            data_set_id="whatsapp-analytics-dataset",
            name="WhatsApp Messages",
            physical_table_map={
                "WhatsAppMessages": quicksight.CfnDataSet.PhysicalTableProperty(
                    custom_sql=quicksight.CfnDataSet.CustomSqlProperty(
                        data_source_arn=data_source.attr_arn,
                        name="WhatsAppMessages",
                        sql_query=f"""
                        SELECT 
                            message_id,
                            event_date,
                            event_time,
                            status,
                            recipient_id,
                            conversation_id,
                            billable,
                            pricing_model,
                            pricing_category,
                            template_name,
                            template_language,
                            year,
                            month,
                            day
                        FROM "{database_name}"."{table_name}"
                        """,
                        columns=[
                            {
                                "name": "message_id",
                                "type": "STRING"
                            },
                            {
                                "name": "event_date",
                                "type": "STRING"
                            },
                            {
                                "name": "event_time",
                                "type": "STRING"
                            },
                            {
                                "name": "aws_account_id",
                                "type": "STRING"
                            },
                            {
                                "name": "status",
                                "type": "STRING"
                            },
                            {
                                "name": "recipient_id",
                                "type": "STRING"
                            },
                            {
                                "name": "conversation_id",
                                "type": "STRING"
                            },
                            {
                                "name": "billable",
                                "type": "BOOLEAN"
                            },
                            {
                                "name": "pricing_model",
                                "type": "STRING"
                            },
                            {
                                "name": "pricing_category",
                                "type": "STRING"
                            },
                            {
                                "name": "template_name",
                                "type": "STRING"
                            },
                            {
                                "name": "template_language",
                                "type": "STRING"
                            },
                            {
                                "name": "year",
                                "type": "INTEGER"
                            },
                            {
                                "name": "month",
                                "type": "INTEGER"
                            },
                            {
                                "name": "day",
                                "type": "INTEGER"
                            }
                        ]
                    )
                )
            },
            logical_table_map={
                "WhatsAppMessages": quicksight.CfnDataSet.LogicalTableProperty(
                    alias="WhatsAppMessages",
                    source=quicksight.CfnDataSet.LogicalTableSourceProperty(
                        physical_table_id="WhatsAppMessages"
                    )
                )
            },
            import_mode="DIRECT_QUERY",
            permissions=[
                quicksight.CfnDataSet.ResourcePermissionProperty(
                    principal=f"arn:aws:quicksight:us-east-1:{quicksight_account_id}:user/default/{quicksight_username}",
                    actions=[
                        "quicksight:DeleteDataSet",
                        "quicksight:UpdateDataSetPermissions",
                        "quicksight:PutDataSetRefreshProperties",
                        "quicksight:CreateRefreshSchedule",
                        "quicksight:CancelIngestion",
                        "quicksight:PassDataSet",
                        "quicksight:UpdateRefreshSchedule",
                        "quicksight:DeleteRefreshSchedule",
                        "quicksight:ListRefreshSchedules",
                        "quicksight:DescribeDataSetRefreshProperties",
                        "quicksight:DescribeDataSet",
                        "quicksight:CreateIngestion",
                        "quicksight:DescribeRefreshSchedule",
                        "quicksight:ListIngestions",
                        "quicksight:DescribeDataSetPermissions",
                        "quicksight:UpdateDataSet",
                        "quicksight:DeleteDataSetRefreshProperties",
                        "quicksight:DescribeIngestion"
                    ]

                )
            ]
        )
        
        # Output the QuickSight console URLs
        CfnOutput(
            self, "QuickSightDatasetURL",
            value=f"https://{self.region}.quicksight.aws.amazon.com/sn/data-sets/{dataset.data_set_id}",
            description="URL to the QuickSight dataset for WhatsApp analytics"
        )        
