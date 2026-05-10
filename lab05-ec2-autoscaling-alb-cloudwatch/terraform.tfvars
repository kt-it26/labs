aws_region           = "us-east-1"
project              = "kt-labs"
environment          = "dev"
instance_type        = "t2.micro"
asg_min_size         = 1
asg_max_size         = 3
asg_desired_capacity = 2
alert_email          = ""  # set to your email to receive alarm notifications
