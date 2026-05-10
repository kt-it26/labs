# kt-it26 | lab05 — EC2 Auto Scaling + ALB + CloudWatch
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      Lab         = "lab05"
      ManagedBy   = "terraform"
    }
  }
}
