# kt-it26 | lab05 — CloudWatch module

resource "aws_sns_topic" "alerts" {
  name = "${var.project}-${var.environment}-asg-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "${var.project}-${var.environment}-cpu-high"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Average"
  threshold           = var.scale_up_cpu_threshold
  alarm_description   = "Scale out: ASG CPU >= ${var.scale_up_cpu_threshold}% for 2 consecutive minutes"
  alarm_actions       = [var.scale_up_policy_arn, aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = {
    AutoScalingGroupName = var.asg_name
  }
}

resource "aws_cloudwatch_metric_alarm" "cpu_low" {
  alarm_name          = "${var.project}-${var.environment}-cpu-low"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 60
  statistic           = "Average"
  threshold           = var.scale_down_cpu_threshold
  alarm_description   = "Scale in: ASG CPU <= ${var.scale_down_cpu_threshold}% for 2 consecutive minutes"
  alarm_actions       = [var.scale_down_policy_arn, aws_sns_topic.alerts.arn]

  dimensions = {
    AutoScalingGroupName = var.asg_name
  }
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project}-${var.environment}-lab05"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "ASG CPU Utilization"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["AWS/EC2", "CPUUtilization", "AutoScalingGroupName", var.asg_name,
              { stat = "Average", period = 60, label = "Avg CPU %" }]
          ]
          annotations = {
            horizontal = [
              { label = "Scale Out ≥${var.scale_up_cpu_threshold}%", value = var.scale_up_cpu_threshold, color = "#ff4444" },
              { label = "Scale In ≤${var.scale_down_cpu_threshold}%", value = var.scale_down_cpu_threshold, color = "#00ff88" }
            ]
          }
          yAxis = { left = { min = 0, max = 100 } }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "ASG Instance Count"
          view   = "timeSeries"
          region = var.aws_region
          metrics = [
            ["AWS/AutoScaling", "GroupDesiredCapacity", "AutoScalingGroupName", var.asg_name,
              { stat = "Average", period = 60, label = "Desired" }],
            ["AWS/AutoScaling", "GroupInServiceCapacity", "AutoScalingGroupName", var.asg_name,
              { stat = "Average", period = 60, label = "In Service" }],
            ["AWS/AutoScaling", "GroupPendingCapacity", "AutoScalingGroupName", var.asg_name,
              { stat = "Average", period = 60, label = "Pending" }]
          ]
        }
      },
      {
        type   = "alarm"
        x      = 0
        y      = 6
        width  = 24
        height = 3
        properties = {
          title  = "Scaling Alarms"
          alarms = [
            aws_cloudwatch_metric_alarm.cpu_high.arn,
            aws_cloudwatch_metric_alarm.cpu_low.arn
          ]
        }
      }
    ]
  })
}
