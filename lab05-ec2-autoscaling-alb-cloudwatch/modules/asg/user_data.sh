#!/bin/bash
# kt-it26 | lab05 — EC2 instance bootstrap
set -euo pipefail

yum install -y httpd
systemctl start httpd
systemctl enable httpd

# IMDSv2-compliant metadata fetch
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/instance-id)
AZ=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/placement/availability-zone)

cat > /var/www/html/index.html <<'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>kt-labs | ASG Demo</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #080b0f;
      color: #c9d1d9;
      font-family: 'JetBrains Mono', 'Courier New', monospace;
      display: flex;
      flex-direction: column;
      min-height: 100vh;
    }
    header {
      background: #0d1117;
      border-bottom: 1px solid #1e3a2f;
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .dots { display: flex; gap: 8px; }
    .dot { width: 12px; height: 12px; border-radius: 50%; }
    .dot-r { background: #ff5f57; }
    .dot-y { background: #febc2e; }
    .dot-g { background: #28c840; }
    .brand { color: #00ff88; font-weight: bold; font-size: 14px; letter-spacing: 2px; }
    main {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 40px 24px;
      gap: 12px;
    }
    .title { color: #00ff88; font-size: 26px; font-weight: bold; text-align: center; }
    .subtitle { color: #8899aa; font-size: 13px; text-align: center; margin-bottom: 28px; }
    .card {
      background: #0d1117;
      border: 1px solid #1e3a2f;
      border-radius: 8px;
      padding: 28px 36px;
      min-width: 360px;
      text-align: center;
    }
    .label {
      color: #8899aa;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 4px;
    }
    .value {
      color: #00ff88;
      font-size: 18px;
      font-weight: bold;
      margin-bottom: 20px;
      word-break: break-all;
    }
    .badge {
      display: inline-block;
      background: #0a2a1a;
      border: 1px solid #00ff88;
      color: #00ff88;
      padding: 4px 14px;
      border-radius: 4px;
      font-size: 12px;
      letter-spacing: 1px;
    }
    footer {
      background: #0d1117;
      border-top: 1px solid #1e3a2f;
      padding: 10px 24px;
      text-align: center;
      color: #8899aa;
      font-size: 11px;
    }
  </style>
</head>
<body>
  <header>
    <div class="dots">
      <div class="dot dot-r"></div>
      <div class="dot dot-y"></div>
      <div class="dot dot-g"></div>
    </div>
    <div class="brand">kt-it26</div>
    <div></div>
  </header>
  <main>
    <div class="title">Auto Scaling Demo</div>
    <div class="subtitle">lab05 &mdash; EC2 Auto Scaling + ALB + CloudWatch</div>
    <div class="card">
      <div class="label">Instance ID</div>
      <div class="value">__INSTANCE_ID__</div>
      <div class="label">Availability Zone</div>
      <div class="value">__AZ__</div>
      <div class="badge">HEALTHY</div>
    </div>
  </main>
  <footer>kt-it26 &mdash; DevOps Portfolio &mdash; lab05</footer>
</body>
</html>
HTMLEOF

sed -i "s/__INSTANCE_ID__/${INSTANCE_ID}/g" /var/www/html/index.html
sed -i "s/__AZ__/${AZ}/g" /var/www/html/index.html
