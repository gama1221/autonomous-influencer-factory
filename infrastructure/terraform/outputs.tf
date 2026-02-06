# infrastructure/terraform/outputs.tf
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "database_endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.chimera.endpoint
  sensitive   = true
}

output "database_name" {
  description = "Database name"
  value       = aws_db_instance.chimera.db_name
}

output "s3_bucket_name" {
  description = "Media S3 bucket name"
  value       = aws_s3_bucket.media.bucket
}

output "ecr_repository_url" {
  description = "ECR repository URL for agent images"
  value       = aws_ecr_repository.agents.repository_url
}

output "api_security_group_id" {
  description = "API security group ID"
  value       = aws_security_group.api.id
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for agents"
  value       = aws_cloudwatch_log_group.agent_logs.name
}

output "agent_iam_role_arn" {
  description = "IAM role ARN for agents"
  value       = aws_iam_role.agent_execution.arn
}

output "openclaw_integration_instructions" {
  description = "Instructions for OpenClaw integration"
  value = <<-EOT
    OpenClaw Integration Setup:
    1. Register agent at: https://api.openclaw.net/agents/register
    2. Use API Key: ${var.openclaw_api_key}
    3. Endpoint URL: https://${aws_db_instance.chimera.endpoint}/api/v1/openclaw
    4. Agent ID will be generated upon registration
    
    Update the config file with:
    - Database URL: ${aws_db_instance.chimera.endpoint}
    - S3 Bucket: ${aws_s3_bucket.media.bucket}
    - CloudWatch Logs: ${aws_cloudwatch_log_group.agent_logs.name}
  EOT
}