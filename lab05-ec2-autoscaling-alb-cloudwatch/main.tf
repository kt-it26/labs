# kt-it26 | lab05 — EC2 Auto Scaling + ALB + CloudWatch

module "networking" {
  source               = "./modules/networking"
  project              = var.project
  environment          = var.environment
  vpc_cidr             = var.vpc_cidr
  availability_zones   = var.availability_zones
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
}

module "alb" {
  source            = "./modules/alb"
  project           = var.project
  environment       = var.environment
  vpc_id            = module.networking.vpc_id
  public_subnet_ids = module.networking.public_subnet_ids
}

module "asg" {
  source                = "./modules/asg"
  project               = var.project
  environment           = var.environment
  vpc_id                = module.networking.vpc_id
  public_subnet_ids     = module.networking.public_subnet_ids
  alb_security_group_id = module.alb.alb_security_group_id
  target_group_arn      = module.alb.target_group_arn
  instance_type         = var.instance_type
  min_size              = var.asg_min_size
  max_size              = var.asg_max_size
  desired_capacity      = var.asg_desired_capacity
}

module "cloudwatch" {
  source                   = "./modules/cloudwatch"
  project                  = var.project
  environment              = var.environment
  aws_region               = var.aws_region
  asg_name                 = module.asg.asg_name
  scale_up_policy_arn      = module.asg.scale_up_policy_arn
  scale_down_policy_arn    = module.asg.scale_down_policy_arn
  scale_up_cpu_threshold   = var.scale_up_cpu_threshold
  scale_down_cpu_threshold = var.scale_down_cpu_threshold
  alert_email              = var.alert_email
}
