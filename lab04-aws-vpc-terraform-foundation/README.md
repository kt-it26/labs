# lab04 — AWS VPC Terraform Foundation

**kt-it26** · DevOps Portfolio · Lab 04/15

Production-grade AWS Virtual Private Cloud built entirely with Terraform.
Multi-AZ architecture with public and private subnets, Internet Gateway,
NAT Gateway, route tables, and security groups — all modularized and ready
for future labs (EC2, EKS, RDS, etc.).

---

## Architecture

```
                        ┌─────────────────────────────────────┐
                        │           AWS Region (us-east-1)     │
                        │                                      │
                        │  ┌────────── VPC 10.0.0.0/16 ───────┐│
                        │  │                                   ││
                        │  │  ┌──────────────────────────────┐ ││
  Internet ─── IGW ──────┤  │  │     Public Subnets           │ ││
                        │  │  │  10.0.1.0/24 (us-east-1a)   │ ││
                        │  │  │  10.0.2.0/24 (us-east-1b)   │ ││
                        │  │  └──────────────┬───────────────┘ ││
                        │  │                 │ NAT GW           ││
                        │  │  ┌──────────────▼───────────────┐ ││
                        │  │  │     Private Subnets           │ ││
                        │  │  │  10.0.11.0/24 (us-east-1a)  │ ││
                        │  │  │  10.0.12.0/24 (us-east-1b)  │ ││
                        │  │  └──────────────────────────────┘ ││
                        │  └───────────────────────────────────┘│
                        └─────────────────────────────────────────┘
```

**Resources created:**
| Resource | Count | Cost |
|---|---|---|
| VPC | 1 | Free |
| Internet Gateway | 1 | Free |
| Public Subnets | 2 | Free |
| Private Subnets | 2 | Free |
| Elastic IP | 1 | Free (while attached) |
| NAT Gateway | 1 | **~$0.045/hr** |
| Route Tables | 2 | Free |
| Security Groups | 3 | Free |

> **Cost warning**: NAT Gateway is the only paid resource. Destroy when done.

---

## Project Structure

```
lab04-aws-vpc-terraform-foundation/
├── main.tf                          # Root: calls modules + security groups
├── variables.tf                     # All input variables with defaults
├── outputs.tf                       # Exports all resource IDs
├── versions.tf                      # Provider versions + default tags
├── terraform.tfvars                 # Default variable values
├── modules/
│   ├── vpc/
│   │   ├── main.tf                  # aws_vpc + aws_internet_gateway
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── subnets/
│       ├── main.tf                  # Subnets + EIP + NAT GW + route tables
│       ├── variables.tf
│       └── outputs.tf
├── environments/
│   └── dev/
│       └── terraform.tfvars         # Dev environment overrides
├── validate.py                      # boto3 infrastructure validator
└── requirements.txt
```

---

## Quick Start

### Prerequisites
```bash
aws configure          # Set your AWS credentials
terraform --version    # Requires >= 1.7.0
python3 --version      # Requires >= 3.10
```

### Deploy
```bash
cd lab04-aws-vpc-terraform-foundation

# Install terraform providers
terraform init

# Preview what will be created (no cost yet)
terraform plan

# Deploy (~3-4 min, NAT GW is the slowest part)
terraform apply

# Verify with boto3 validator
pip3 install -r requirements.txt
python3 validate.py
```

### Destroy (always do this when done)
```bash
terraform destroy
```

---

## Terraform Outputs

After `terraform apply`, these outputs are available:

```bash
terraform output vpc_id              # VPC ID
terraform output public_subnet_ids   # ["subnet-xxx", "subnet-yyy"]
terraform output private_subnet_ids  # ["subnet-aaa", "subnet-bbb"]
terraform output nat_gateway_id      # NAT GW ID
terraform output sg_bastion_id       # Security group for SSH bastion
terraform output sg_web_id           # Security group for HTTP/HTTPS
terraform output sg_internal_id      # Security group for internal services
```

---

## boto3 Validator

`validate.py` connects to AWS via boto3 and verifies every resource:

```
╔══════════════════════════════════════════════════════╗
║        kt-it26 — VPC Infrastructure Validator        ║
╚══════════════════════════════════════════════════════╝

[VPC]
  ✓ PASS  VPC exists             (vpc-0abc123)
  ✓ PASS  VPC CIDR matches       (10.0.0.0/16 == 10.0.0.0/16)
  ✓ PASS  DNS hostnames enabled
  ✓ PASS  DNS support enabled

[Internet Gateway]
  ✓ PASS  IGW exists             (igw-0xyz789)
  ✓ PASS  IGW attached to VPC

[Subnets]
  ✓ PASS  Public subnet exists   (subnet-pub1)
  ✓ PASS    Public subnet maps public IP
  ✓ PASS  Private subnet exists  (subnet-priv1)
  ✓ PASS    Private subnet does NOT map public IP
  ...

[Route Tables]
  ✓ PASS  Public RT → IGW (0.0.0.0/0)
  ✓ PASS  Private RT → NAT GW (0.0.0.0/0)

  Summary: 18/18 checks passed — infrastructure is healthy!
```

---

## Security Groups

| SG | Inbound | Use case |
|---|---|---|
| `bastion-sg` | TCP 22 (0.0.0.0/0) | SSH jump host |
| `web-sg` | TCP 80, 443 (0.0.0.0/0) | Public-facing web servers |
| `internal-sg` | All (VPC CIDR only) | Databases, internal services |

---

## Skills Demonstrated

- **Terraform modules** — reusable, parameterized modules for VPC and subnets
- **AWS networking** — VPC, subnets, IGW, NAT Gateway, route tables, EIP
- **Multi-AZ design** — redundant subnets across 2 availability zones
- **Infrastructure validation** — boto3 script verifies actual AWS state, not just Terraform state
- **Cost awareness** — `enable_nat_gateway` flag to control the only paid resource
- **Tagging strategy** — consistent tags via provider `default_tags`
- **Security groups** — layered access control (public, web, internal tiers)

---

## Part of kt-it26 DevOps Portfolio

| Lab | Stack | Status |
|---|---|---|
| lab01 | Python · psutil · Flask · systemd | ✓ |
| lab02 | Python · Bash · argparse · HTML reports | ✓ |
| lab03 | FastAPI · AsyncIO · WebSockets · Claude AI | ✓ |
| **lab04** | **Terraform · AWS VPC · boto3** | **✓** |
| lab05 | Terraform · EC2 · Auto Scaling · ALB | — |
| lab06 | Terraform workspaces · S3 backend · DynamoDB | — |
| ... | ... | — |

---

*kt-it26 — built on Linux, deployed to AWS, validated with Python*
