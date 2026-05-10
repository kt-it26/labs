# lab05 — EC2 Auto Scaling + ALB + CloudWatch

**kt-it26** · DevOps Portfolio · Lab 05/15

Production-pattern auto-scaling web tier built entirely with Terraform.
An Application Load Balancer distributes traffic across EC2 instances managed
by an Auto Scaling Group, with CloudWatch alarms that automatically scale out
under CPU load and scale in when traffic drops.

---

## Architecture

```
                          Internet
                             │
                    ┌────────▼────────┐
                    │   ALB (HTTP:80) │  ← internet-facing
                    │  public-1a  1b  │
                    └────────┬────────┘
                             │ HTTP :80
                   ┌─────────▼──────────┐
                   │    Target Group     │  ← health checks /
                   └──────┬──────┬──────┘
                          │      │
               ┌──────────▼─┐  ┌─▼──────────┐
               │  EC2 t2.   │  │  EC2 t2.   │  ← ASG instances
               │  micro     │  │  micro     │     IMDSv2 enforced
               │  us-e-1a   │  │  us-e-1b   │
               └────────────┘  └────────────┘
                    ╔══════════════════════╗
                    ║  Auto Scaling Group  ║  min=1  desired=2  max=3
                    ╚══════════════════════╝
                             │
                    ┌────────▼────────┐
                    │   CloudWatch    │
                    │  CPU ≥ 70% → +1 │
                    │  CPU ≤ 30% → -1 │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   SNS Topic     │  ← optional email alerts
                    └─────────────────┘
```

**Resources created:**
| Resource | Count | Cost |
|---|---|---|
| VPC | 1 | Free |
| Internet Gateway | 1 | Free |
| Public Subnets | 2 | Free |
| Private Subnets | 2 | Free |
| Application Load Balancer | 1 | ~$0.008/hr |
| EC2 t2.micro instances | 2 (desired) | Free tier eligible |
| Auto Scaling Group | 1 | Free |
| Launch Template | 1 | Free |
| CloudWatch Alarms | 2 | Free tier: 10 alarms |
| CloudWatch Dashboard | 1 | Free tier: 3 dashboards |
| SNS Topic | 1 | Free |

> **Cost note**: ALB is the only continuously billed resource (~$0.19/day). Destroy when done.

---

## Project Structure

```
lab05-ec2-autoscaling-alb-cloudwatch/
├── main.tf                          # Root: wires all 4 modules together
├── variables.tf                     # All input variables with defaults
├── outputs.tf                       # ALB URL, dashboard link, ASG name
├── versions.tf                      # Provider pin + default_tags
├── terraform.tfvars                 # Default values
├── modules/
│   ├── networking/
│   │   ├── main.tf                  # VPC, IGW, public/private subnets, route tables
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── alb/
│   │   ├── main.tf                  # ALB, target group, HTTP listener, ALB SG
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── asg/
│   │   ├── main.tf                  # Launch template, ASG, scale-out/in policies, EC2 SG
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── user_data.sh             # Amazon Linux 2 bootstrap: httpd + branded status page
│   └── cloudwatch/
│       ├── main.tf                  # CPU alarms, SNS topic, dashboard
│       ├── variables.tf
│       └── outputs.tf
├── validate.py                      # boto3 validator: 18 checks across all resources
└── requirements.txt
```

---

## Quick Start

### Prerequisites
```bash
aws configure          # Set your AWS credentials
terraform --version    # Requires >= 1.5
python3 --version      # Requires >= 3.10
```

### Deploy
```bash
cd lab05-ec2-autoscaling-alb-cloudwatch

terraform init
terraform plan
terraform apply        # ~4-5 min (ALB provisioning is the slow part)

# Validate with boto3
pip3 install -r requirements.txt
python3 validate.py
```

After apply, open the ALB URL in your browser:
```bash
terraform output alb_url
```

Reload several times — you'll see different instance IDs as the ALB round-robins across AZs.

### Destroy
```bash
terraform destroy
```

---

## Terraform Outputs

```bash
terraform output alb_url                  # http://kt-labs-dev-alb-xxx.us-east-1.elb.amazonaws.com
terraform output asg_name                 # kt-labs-dev-asg
terraform output cloudwatch_dashboard_url # https://us-east-1.console.aws.amazon.com/cloudwatch/...
terraform output vpc_id                   # vpc-0abc123
terraform output target_group_arn         # arn:aws:elasticloadbalancing:...
```

---

## boto3 Validator

`validate.py` connects to AWS and runs 18 checks across ALB, target group, ASG,
scaling policies, and CloudWatch alarms:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  kt-it26 | lab05 validator — ASG + ALB + CloudWatch
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Application Load Balancer
  [PASS]  ALB exists                → kt-labs-dev-alb
  [PASS]  ALB state is active       → active
  [PASS]  ALB is internet-facing    → internet-facing
  [PASS]  ALB spans 2+ AZs         → 2 AZs

  Target Group
  [PASS]  Target group exists       → kt-labs-dev-tg
  [PASS]  At least 1 healthy target → 2/2 healthy

  Auto Scaling Group
  [PASS]  ASG exists                → kt-labs-dev-asg
  [PASS]  Desired capacity >= 1     → desired=2
  [PASS]  Min/max configured        → min=1  max=3
  [PASS]  At least 1 instance InService → 2 InService
  [PASS]  Health check type is ELB  → ELB

  Scaling Policies
  [PASS]  Scale-out policy exists   → kt-labs-dev-scale-up
  [PASS]  Scale-in policy exists    → kt-labs-dev-scale-down
  [PASS]  Scale-out adds instances  → ScalingAdjustment=1
  [PASS]  Scale-in removes instances → ScalingAdjustment=-1

  CloudWatch Alarms
  [PASS]  Alarm exists: kt-labs-dev-cpu-high
  [PASS]    └─ has alarm actions    → 2 action(s)
  [PASS]  Alarm exists: kt-labs-dev-cpu-low

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Result: 18/18 checks passed
  Infrastructure is healthy ✓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Testing Auto Scaling

Trigger a manual scale-out by forcing CPU stress on a running instance:

```bash
# Get an instance ID from the ASG
aws autoscaling describe-auto-scaling-groups \
  --auto-scaling-group-names kt-labs-dev-asg \
  --query 'AutoScalingGroups[0].Instances[*].InstanceId' \
  --output text

# Connect via SSM Session Manager (no SSH key needed)
aws ssm start-session --target <instance-id>

# Inside the instance — stress CPU for 5 minutes
dd if=/dev/zero of=/dev/null &
# Wait ~2 min, then check ASG activity
```

Watch the CloudWatch dashboard to see:
1. CPU alarm transitions to ALARM state
2. ASG desired capacity increments
3. New instance joins the target group as healthy

---

## Security Design

| Component | Access control |
|---|---|
| ALB Security Group | Inbound HTTP:80 from `0.0.0.0/0` |
| EC2 Security Group | Inbound HTTP:80 from ALB SG **only** — no direct internet access |
| IMDSv2 | Enforced via launch template `http_tokens = "required"` |
| Credentials | AWS profile via `aws configure` — no keys in code |

---

## Skills Demonstrated

- **Auto Scaling Group** — launch template, multi-AZ placement, ELB health checks
- **Application Load Balancer** — target group registration, health check tuning
- **CloudWatch alarms** — metric-based scaling triggers with SNS notifications
- **CloudWatch dashboard** — CPU utilization + instance count widgets with threshold annotations
- **Security best practices** — EC2 SG locked to ALB SG, IMDSv2 enforced
- **Terraform modules** — 4 independent modules wired via root outputs/inputs
- **boto3 validation** — 18 checks verify actual AWS state post-deploy

---

## Part of kt-it26 DevOps Portfolio

| Lab | Stack | Status |
|---|---|---|
| lab01 | Python · psutil · Flask · systemd | ✓ |
| lab02 | Python · Bash · argparse · HTML reports | ✓ |
| lab03 | FastAPI · AsyncIO · WebSockets · Claude AI | ✓ |
| lab04 | Terraform · AWS VPC · boto3 | ✓ |
| **lab05** | **Terraform · EC2 · Auto Scaling · ALB · CloudWatch** | **✓** |
| lab06 | Terraform workspaces · S3 backend · DynamoDB state lock | — |
| lab07 | Lambda · API Gateway · DynamoDB · pytest | — |
| ... | ... | — |

---

*kt-it26 — built on Linux, deployed to AWS, validated with Python*
