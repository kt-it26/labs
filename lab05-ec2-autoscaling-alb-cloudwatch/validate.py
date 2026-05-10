#!/usr/bin/env python3
"""
kt-it26 | lab05 — boto3 validator for EC2 Auto Scaling + ALB + CloudWatch
"""

import sys
import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
PROJECT = "kt-labs"
ENV = "dev"
PREFIX = f"{PROJECT}-{ENV}"

GREEN = "\033[92m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def check(label: str, passed: bool, detail: str = "") -> bool:
    status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    line = f"  [{status}]  {label}"
    if detail:
        line += f"  {DIM}→  {detail}{RESET}"
    print(line)
    return passed


def section(title: str) -> None:
    print(f"\n{BOLD}  {title}{RESET}")


def main() -> None:
    print(f"\n{GREEN}{'━' * 58}{RESET}")
    print(f"{BOLD}  kt-it26 | lab05 validator — ASG + ALB + CloudWatch{RESET}")
    print(f"{GREEN}{'━' * 58}{RESET}")

    try:
        elbv2 = boto3.client("elbv2", region_name=REGION)
        autoscaling = boto3.client("autoscaling", region_name=REGION)
        cloudwatch = boto3.client("cloudwatch", region_name=REGION)
    except Exception as exc:
        print(f"\n{RED}  ERROR: Could not initialise boto3 clients — {exc}{RESET}\n")
        sys.exit(1)

    results: list[bool] = []

    # --- ALB ---
    section("Application Load Balancer")
    try:
        albs = elbv2.describe_load_balancers()["LoadBalancers"]
        alb = next((a for a in albs if a["LoadBalancerName"] == f"{PREFIX}-alb"), None)
        results.append(check("ALB exists", alb is not None, f"{PREFIX}-alb"))
        if alb:
            state = alb["State"]["Code"]
            results.append(check("ALB state is active", state == "active", state))
            scheme = alb["Scheme"]
            results.append(check("ALB is internet-facing", scheme == "internet-facing", scheme))
            results.append(check("ALB spans 2+ AZs", len(alb["AvailabilityZones"]) >= 2,
                                  f"{len(alb['AvailabilityZones'])} AZs"))
    except ClientError as exc:
        print(f"  {RED}ERROR: {exc}{RESET}")
        results.append(False)

    # --- Target Group ---
    section("Target Group")
    tg = None
    try:
        tgs = elbv2.describe_target_groups()["TargetGroups"]
        tg = next((t for t in tgs if t["TargetGroupName"] == f"{PREFIX}-tg"), None)
        results.append(check("Target group exists", tg is not None, f"{PREFIX}-tg"))
        if tg:
            health = elbv2.describe_target_health(TargetGroupArn=tg["TargetGroupArn"])
            all_targets = health["TargetHealthDescriptions"]
            healthy = [h for h in all_targets if h["TargetHealth"]["State"] == "healthy"]
            results.append(check("At least 1 healthy target", len(healthy) >= 1,
                                  f"{len(healthy)}/{len(all_targets)} healthy"))
    except ClientError as exc:
        print(f"  {RED}ERROR: {exc}{RESET}")
        results.append(False)

    # --- Auto Scaling Group ---
    section("Auto Scaling Group")
    asg = None
    try:
        resp = autoscaling.describe_auto_scaling_groups(
            AutoScalingGroupNames=[f"{PREFIX}-asg"]
        )
        asgs = resp["AutoScalingGroups"]
        asg = asgs[0] if asgs else None
        results.append(check("ASG exists", asg is not None, f"{PREFIX}-asg"))
        if asg:
            desired = asg["DesiredCapacity"]
            results.append(check("Desired capacity >= 1", desired >= 1, f"desired={desired}"))
            min_s, max_s = asg["MinSize"], asg["MaxSize"]
            results.append(check("Min/max configured correctly", min_s >= 1 and max_s > min_s,
                                  f"min={min_s}  max={max_s}"))
            in_service = [i for i in asg["Instances"] if i["LifecycleState"] == "InService"]
            results.append(check("At least 1 instance InService", len(in_service) >= 1,
                                  f"{len(in_service)} InService"))
            hc_type = asg["HealthCheckType"]
            results.append(check("Health check type is ELB", hc_type == "ELB", hc_type))
    except ClientError as exc:
        print(f"  {RED}ERROR: {exc}{RESET}")
        results.append(False)

    # --- Scaling Policies ---
    section("Scaling Policies")
    try:
        policies = autoscaling.describe_policies(
            AutoScalingGroupName=f"{PREFIX}-asg"
        )["ScalingPolicies"]
        scale_up = next((p for p in policies if "scale-up" in p["PolicyName"]), None)
        scale_down = next((p for p in policies if "scale-down" in p["PolicyName"]), None)
        results.append(check("Scale-out policy exists", scale_up is not None,
                              scale_up["PolicyName"] if scale_up else ""))
        results.append(check("Scale-in policy exists", scale_down is not None,
                              scale_down["PolicyName"] if scale_down else ""))
        if scale_up:
            adj = scale_up.get("ScalingAdjustment", 0)
            results.append(check("Scale-out adds instances", adj > 0, f"ScalingAdjustment={adj}"))
        if scale_down:
            adj = scale_down.get("ScalingAdjustment", 0)
            results.append(check("Scale-in removes instances", adj < 0, f"ScalingAdjustment={adj}"))
    except ClientError as exc:
        print(f"  {RED}ERROR: {exc}{RESET}")
        results.append(False)

    # --- CloudWatch Alarms ---
    section("CloudWatch Alarms")
    try:
        alarm_names = [f"{PREFIX}-cpu-high", f"{PREFIX}-cpu-low"]
        alarms_resp = cloudwatch.describe_alarms(AlarmNames=alarm_names)["MetricAlarms"]
        for name in alarm_names:
            alarm = next((a for a in alarms_resp if a["AlarmName"] == name), None)
            results.append(check(f"Alarm exists: {name}", alarm is not None))
            if alarm:
                actions = alarm.get("AlarmActions", [])
                results.append(check(f"  └─ has alarm actions", len(actions) > 0,
                                      f"{len(actions)} action(s)"))
    except ClientError as exc:
        print(f"  {RED}ERROR: {exc}{RESET}")
        results.append(False)

    # --- Summary ---
    passed = sum(1 for r in results if r)
    total = len(results)
    color = GREEN if passed == total else RED
    print(f"\n{GREEN}{'━' * 58}{RESET}")
    print(f"  {color}{BOLD}Result: {passed}/{total} checks passed{RESET}")
    if passed == total:
        print(f"  {GREEN}Infrastructure is healthy ✓{RESET}")
    else:
        print(f"  {RED}{total - passed} check(s) failed — review output above{RESET}")
    print(f"{GREEN}{'━' * 58}{RESET}\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
