output "asg_name" {
  description = "Name of the Auto Scaling Group"
  value       = aws_autoscaling_group.main.name
}

output "scale_up_policy_arn" {
  description = "ARN of the scale-out policy"
  value       = aws_autoscaling_policy.scale_up.arn
}

output "scale_down_policy_arn" {
  description = "ARN of the scale-in policy"
  value       = aws_autoscaling_policy.scale_down.arn
}

output "launch_template_id" {
  description = "ID of the launch template"
  value       = aws_launch_template.main.id
}

output "ec2_security_group_id" {
  description = "Security group ID for ASG instances"
  value       = aws_security_group.ec2.id
}
