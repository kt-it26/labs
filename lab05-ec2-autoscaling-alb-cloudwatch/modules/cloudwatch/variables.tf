variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "aws_region" {
  type = string
}

variable "asg_name" {
  type = string
}

variable "scale_up_policy_arn" {
  type = string
}

variable "scale_down_policy_arn" {
  type = string
}

variable "scale_up_cpu_threshold" {
  type = number
}

variable "scale_down_cpu_threshold" {
  type = number
}

variable "alert_email" {
  type = string
}
