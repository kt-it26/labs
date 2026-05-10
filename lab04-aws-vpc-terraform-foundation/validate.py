#!/usr/bin/env python3
"""
kt-it26 — lab04: AWS VPC Infrastructure Validator
Reads terraform outputs and verifies every resource exists and is correctly
configured using boto3. Exits 0 if all checks pass, 1 if any fail.
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# --- Terminal colors ---
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

PASS = f"{GREEN}✓ PASS{RESET}"
FAIL = f"{RED}✗ FAIL{RESET}"
WARN = f"{YELLOW}⚠ WARN{RESET}"


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def banner() -> None:
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════╗
║        kt-it26 — VPC Infrastructure Validator        ║
║              lab04-aws-vpc-terraform-foundation       ║
╚══════════════════════════════════════════════════════╝{RESET}
""")


def get_terraform_outputs() -> dict:
    """Run terraform output -json and parse the result."""
    try:
        result = subprocess.run(
            ["terraform", "output", "-json"],
            capture_output=True, text=True, check=True
        )
        raw = json.loads(result.stdout)
        return {k: v["value"] for k, v in raw.items()}
    except subprocess.CalledProcessError as e:
        print(f"{RED}ERROR: terraform output failed — have you run terraform apply?{RESET}")
        print(e.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"{RED}ERROR: Could not parse terraform output JSON{RESET}")
        sys.exit(1)


def check(label: str, condition: bool, detail: str = "") -> CheckResult:
    result = CheckResult(name=label, passed=condition, detail=detail)
    status = PASS if condition else FAIL
    line = f"  {status}  {label}"
    if detail:
        line += f"  {YELLOW}({detail}){RESET}"
    print(line)
    return result


def validate_vpc(ec2, vpc_id: str, expected_cidr: str) -> list[CheckResult]:
    print(f"\n{BOLD}[VPC]{RESET}")
    results = []

    try:
        resp = ec2.describe_vpcs(VpcIds=[vpc_id])
        vpcs = resp["Vpcs"]
        results.append(check("VPC exists", bool(vpcs), vpc_id))
        if vpcs:
            vpc = vpcs[0]
            results.append(check(
                "VPC CIDR matches",
                vpc["CidrBlock"] == expected_cidr,
                f"{vpc['CidrBlock']} == {expected_cidr}"
            ))
            dns_hostnames = ec2.describe_vpc_attribute(
                VpcId=vpc_id, Attribute="enableDnsHostnames"
            )["EnableDnsHostnames"]["Value"]
            results.append(check("DNS hostnames enabled", dns_hostnames))

            dns_support = ec2.describe_vpc_attribute(
                VpcId=vpc_id, Attribute="enableDnsSupport"
            )["EnableDnsSupport"]["Value"]
            results.append(check("DNS support enabled", dns_support))
            results.append(check(
                "VPC state available",
                vpc["State"] == "available",
                vpc["State"]
            ))
    except ClientError as e:
        results.append(check("VPC exists", False, str(e)))

    return results


def validate_igw(ec2, igw_id: str, vpc_id: str) -> list[CheckResult]:
    print(f"\n{BOLD}[Internet Gateway]{RESET}")
    results = []

    try:
        resp = ec2.describe_internet_gateways(InternetGatewayIds=[igw_id])
        igws = resp["InternetGateways"]
        results.append(check("IGW exists", bool(igws), igw_id))
        if igws:
            igw = igws[0]
            attachments = igw.get("Attachments", [])
            attached_vpcs = [a["VpcId"] for a in attachments if a["State"] == "available"]
            results.append(check(
                "IGW attached to VPC",
                vpc_id in attached_vpcs,
                f"attached to: {attached_vpcs}"
            ))
    except ClientError as e:
        results.append(check("IGW exists", False, str(e)))

    return results


def validate_subnets(ec2, public_ids: list, private_ids: list) -> list[CheckResult]:
    print(f"\n{BOLD}[Subnets]{RESET}")
    results = []
    all_ids = public_ids + private_ids

    try:
        resp = ec2.describe_subnets(SubnetIds=all_ids)
        found = {s["SubnetId"]: s for s in resp["Subnets"]}

        for sid in public_ids:
            subnet = found.get(sid, {})
            results.append(check(f"Public subnet exists {sid}", bool(subnet)))
            if subnet:
                results.append(check(
                    f"  Public subnet maps public IP",
                    subnet.get("MapPublicIpOnLaunch", False),
                ))

        for sid in private_ids:
            subnet = found.get(sid, {})
            results.append(check(f"Private subnet exists {sid}", bool(subnet)))
            if subnet:
                results.append(check(
                    f"  Private subnet does NOT map public IP",
                    not subnet.get("MapPublicIpOnLaunch", True),
                ))

    except ClientError as e:
        results.append(check("Subnets exist", False, str(e)))

    return results


def validate_nat_gateway(ec2, nat_id: str) -> list[CheckResult]:
    print(f"\n{BOLD}[NAT Gateway]{RESET}")
    results = []

    if not nat_id:
        results.append(check("NAT Gateway", True, "disabled — skipping"))
        return results

    try:
        resp = ec2.describe_nat_gateways(NatGatewayIds=[nat_id])
        nats = resp["NatGateways"]
        results.append(check("NAT Gateway exists", bool(nats), nat_id))
        if nats:
            nat = nats[0]
            results.append(check(
                "NAT Gateway state available",
                nat["State"] == "available",
                nat["State"]
            ))
            has_eip = bool(nat.get("NatGatewayAddresses", []))
            results.append(check("NAT Gateway has EIP", has_eip))
    except ClientError as e:
        results.append(check("NAT Gateway exists", False, str(e)))

    return results


def validate_route_tables(ec2, public_rt_id: str, private_rt_id: str,
                           igw_id: str, nat_id: str) -> list[CheckResult]:
    print(f"\n{BOLD}[Route Tables]{RESET}")
    results = []

    try:
        resp = ec2.describe_route_tables(RouteTableIds=[public_rt_id, private_rt_id])
        rt_map = {rt["RouteTableId"]: rt for rt in resp["RouteTables"]}

        # Public RT: must have 0.0.0.0/0 → IGW
        pub_rt = rt_map.get(public_rt_id, {})
        results.append(check("Public route table exists", bool(pub_rt), public_rt_id))
        if pub_rt:
            routes = pub_rt.get("Routes", [])
            igw_route = any(
                r.get("DestinationCidrBlock") == "0.0.0.0/0" and r.get("GatewayId") == igw_id
                for r in routes
            )
            results.append(check("Public RT → IGW (0.0.0.0/0)", igw_route))

        # Private RT: must have 0.0.0.0/0 → NAT GW (if NAT enabled)
        priv_rt = rt_map.get(private_rt_id, {})
        results.append(check("Private route table exists", bool(priv_rt), private_rt_id))
        if priv_rt and nat_id:
            routes = priv_rt.get("Routes", [])
            nat_route = any(
                r.get("DestinationCidrBlock") == "0.0.0.0/0" and r.get("NatGatewayId") == nat_id
                for r in routes
            )
            results.append(check("Private RT → NAT GW (0.0.0.0/0)", nat_route))

    except ClientError as e:
        results.append(check("Route tables", False, str(e)))

    return results


def validate_security_groups(ec2, sg_ids: dict) -> list[CheckResult]:
    print(f"\n{BOLD}[Security Groups]{RESET}")
    results = []

    try:
        resp = ec2.describe_security_groups(GroupIds=list(sg_ids.values()))
        found = {sg["GroupId"]: sg for sg in resp["SecurityGroups"]}

        for name, sg_id in sg_ids.items():
            sg = found.get(sg_id, {})
            results.append(check(f"SG {name} exists", bool(sg), sg_id))

    except ClientError as e:
        results.append(check("Security groups", False, str(e)))

    return results


def print_summary(results: list[CheckResult]) -> None:
    total  = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    print(f"""
{BOLD}{'═' * 54}
  Summary: {passed}/{total} checks passed
{'═' * 54}{RESET}""")

    if failed == 0:
        print(f"  {GREEN}{BOLD}All checks passed — infrastructure is healthy!{RESET}")
    else:
        print(f"  {RED}{BOLD}{failed} check(s) failed — review output above{RESET}")
        failed_names = [r.name for r in results if not r.passed]
        for name in failed_names:
            print(f"  {RED}✗ {name}{RESET}")


def main() -> None:
    banner()

    print(f"{CYAN}Reading terraform outputs...{RESET}")
    outputs = get_terraform_outputs()

    region     = outputs.get("aws_region", "us-east-1")
    vpc_id     = outputs["vpc_id"]
    vpc_cidr   = outputs["vpc_cidr"]
    igw_id     = outputs["igw_id"]
    nat_id     = outputs.get("nat_gateway_id", "")
    pub_rt_id  = outputs["public_route_table_id"]
    priv_rt_id = outputs["private_route_table_id"]
    pub_subs   = outputs["public_subnet_ids"]
    priv_subs  = outputs["private_subnet_ids"]
    sg_ids     = {
        "bastion":  outputs["sg_bastion_id"],
        "web":      outputs["sg_web_id"],
        "internal": outputs["sg_internal_id"],
    }

    print(f"Region: {CYAN}{region}{RESET}  |  VPC: {CYAN}{vpc_id}{RESET}\n")

    try:
        ec2 = boto3.client("ec2", region_name=region)
    except NoCredentialsError:
        print(f"{RED}ERROR: No AWS credentials found. Run 'aws configure'.{RESET}")
        sys.exit(1)

    all_results: list[CheckResult] = []
    all_results += validate_vpc(ec2, vpc_id, vpc_cidr)
    all_results += validate_igw(ec2, igw_id, vpc_id)
    all_results += validate_subnets(ec2, pub_subs, priv_subs)
    all_results += validate_nat_gateway(ec2, nat_id)
    all_results += validate_route_tables(ec2, pub_rt_id, priv_rt_id, igw_id, nat_id)
    all_results += validate_security_groups(ec2, sg_ids)

    print_summary(all_results)

    failed = sum(1 for r in all_results if not r.passed)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
