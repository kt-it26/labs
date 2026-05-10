output "vpc_id" {
  description = "ID of the created VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC"
  value       = module.vpc.vpc_cidr
}

output "igw_id" {
  description = "ID of the Internet Gateway"
  value       = module.vpc.igw_id
}

output "public_subnet_ids" {
  description = "List of public subnet IDs"
  value       = module.subnets.public_subnet_ids
}

output "private_subnet_ids" {
  description = "List of private subnet IDs"
  value       = module.subnets.private_subnet_ids
}

output "nat_gateway_id" {
  description = "ID of the NAT Gateway (empty if disabled)"
  value       = module.subnets.nat_gateway_id
}

output "public_route_table_id" {
  description = "ID of the public route table"
  value       = module.subnets.public_route_table_id
}

output "private_route_table_id" {
  description = "ID of the private route table"
  value       = module.subnets.private_route_table_id
}

output "sg_bastion_id" {
  description = "Security group ID for bastion hosts"
  value       = aws_security_group.bastion.id
}

output "sg_web_id" {
  description = "Security group ID for web servers"
  value       = aws_security_group.web.id
}

output "sg_internal_id" {
  description = "Security group ID for internal services"
  value       = aws_security_group.internal.id
}

output "aws_region" {
  description = "AWS region where resources are deployed"
  value       = var.aws_region
}
