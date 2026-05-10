output "alb_url" {
  description = "URL of the Application Load Balancer — open in browser to see the demo"
  value       = "http://${module.alb.alb_dns_name}"
}

output "asg_name" {
  description = "Name of the Auto Scaling Group"
  value       = module.asg.asg_name
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "target_group_arn" {
  description = "ARN of the ALB target group"
  value       = module.alb.target_group_arn
}

output "cloudwatch_dashboard_url" {
  description = "CloudWatch dashboard link (opens in AWS console)"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${module.cloudwatch.dashboard_name}"
}

output "sns_topic_arn" {
  description = "SNS topic ARN for alarm notifications"
  value       = module.cloudwatch.sns_topic_arn
}
