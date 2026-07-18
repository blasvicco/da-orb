# Orb — AWS Infrastructure & Security

This document describes how Orb is deployed on Amazon Web Services (AWS), what security controls are in place, and how Orb connects to an organization's internal systems without exposing them to the internet.

---

## Infrastructure overview

Orb runs entirely on AWS using managed, enterprise-grade services. Every component is isolated inside a private network. Only the surfaces that need to be reached by end users are exposed — everything else is locked away inside the cloud environment and unreachable from the outside world.

```
                  ┌─────────────────────────────────────────────┐
                  │                  Internet                   │
                  └───────────────────┬─────────────────────────┘
                                      │ HTTPS only
                  ┌───────────────────▼─────────────────────────┐
                  │           CloudFront + S3                   │
                  │        (Frontend — static assets)           │
                  │      Encrypted in transit and at rest       │
                  └───────────────────┬─────────────────────────┘
                                      │ HTTPS only
                  ┌───────────────────▼─────────────────────────┐
                  │         Application Load Balancer           │
                  │           (Public — HTTPS only)             │
                  └───────────────────┬─────────────────────────┘
                                      │
          ┌───────────────────────────▼────────────────────────────────┐
          │                    AWS VPC — Private Network               │
          │                                                            │
          │  ┌──────────────────────────────────────────────────────┐  │
          │  │              Public Subnet                           │  │
          │  │   ALB (terminates TLS, routes to private services)   │  │
          │  └───────────────────────┬──────────────────────────────┘  │
          │                          │                                 │
          │  ┌───────────────────────▼──────────────────────────────┐  │
          │  │              Private Subnet                          │  │
          │  │                                                      │  │
          │  │   ECS Fargate Cluster                                │  │
          │  │   ├── backend      (Gunicorn — API, public-facing)   │  │
          │  │   ├── n8n-main     (Workflow editor — internal only) │  │
          │  │   ├── n8n-webhook  (Webhook receiver — internal only)│  │
          │  │   ├── n8n-worker   (Execution — internal only)       │  │
          │  │   └── github-mcp   (MCP server — internal only)      │  │
          │  │                                                      │  │
          │  │   RDS Aurora PostgreSQL   (private subnet only)      │  │
          │  │   ElastiCache Redis       (private subnet only)      │  │
          │  └──────────────────────────────────────────────────────┘  │
          └────────────────────────────────────────────────────────────┘
```

---

## Services

### Compute — AWS ECS Fargate

All Orb services run as containers on **ECS Fargate** — AWS's serverless container platform. There are no servers to patch or manage. AWS handles the underlying infrastructure; Orb manages only the application containers.

| Service | Visibility | Role |
|---|---|---|
| `backend` (Gunicorn) | Public (via ALB + HTTPS) | REST API and WebSocket endpoint |
| `n8n-main` | Internal only | Workflow editor and management |
| `n8n-webhook` | Internal only | Receives orchestration callbacks |
| `n8n-worker` | Internal only | Executes workflows in the background |
| `github-mcp` | Internal only | MCP tool server for GitHub integration |

Only the **backend** service is reachable from outside the VPC, and only through the Application Load Balancer over HTTPS. All n8n services and MCP tools have no public exposure.

---

### Database — Amazon RDS Aurora (PostgreSQL)

Orb uses **Amazon RDS Aurora PostgreSQL** for all persistent data: chat sessions, message history, and organization configuration.

- **Encryption at rest** — All data is encrypted using AES-256 via AWS Key Management Service (KMS). This applies to the database storage, automated backups, and snapshots.
- **Encryption in transit** — All connections to Aurora require TLS. Unencrypted connections are rejected.
- **Private subnet only** — Aurora is deployed in a private subnet with no public IP address. It is reachable only by ECS services within the same VPC.
- **Automated backups** — Point-in-time recovery enabled. Backups are retained and encrypted.
- **High availability** — Aurora replicates data across multiple Availability Zones automatically.

---

### Cache — Amazon ElastiCache (Redis)

Orb uses **Amazon ElastiCache for Redis** for real-time WebSocket message brokering and session caching.

- **Private subnet only** — ElastiCache has no public endpoint. It is reachable exclusively by ECS services within the VPC.
- **Encryption in transit** — TLS enforced on all connections.
- **Encryption at rest** — Data stored in Redis is encrypted at rest.
- **No internet exposure** — Security groups block all access except from ECS task security groups.

---

### Frontend — Amazon CloudFront + S3

The Orb web application (HTML, CSS, JavaScript) is built as a static bundle and served through **Amazon CloudFront** backed by **Amazon S3**.

- **CloudFront** acts as the global content delivery network (CDN), serving the application from edge locations close to users for low latency.
- **HTTPS only** — HTTP requests are automatically redirected to HTTPS. TLS is enforced end-to-end.
- **S3 encryption at rest** — All static assets in S3 are encrypted using AES-256 (SSE-S3 or SSE-KMS).
- **No public S3 access** — The S3 bucket has public access blocked. CloudFront is the only authorized origin, using an Origin Access Control (OAC) policy.
- **Custom domain + ACM certificate** — TLS certificates are managed by AWS Certificate Manager (ACM) at no extra cost, with automatic renewal.

---

### Networking — Amazon VPC

All backend services live inside a dedicated **Amazon VPC** (Virtual Private Cloud) with strict network segmentation.

- **Public subnet** — Contains only the Application Load Balancer. No application services are placed here.
- **Private subnets** — All ECS services, RDS Aurora, and ElastiCache live here, isolated from the internet.
- **Security groups** — Act as virtual firewalls. Each service only allows inbound traffic from specific sources (e.g., Aurora only accepts connections from ECS task security groups; ElastiCache only from ECS tasks).
- **NAT Gateway** — Private subnet services can initiate outbound calls (e.g., to SAP APIs or external services) without being reachable from the internet.
- **VPC Flow Logs** — All network traffic is logged for audit and anomaly detection.

---

### Identity & access — AWS IAM

- Each ECS service runs under its own **IAM Task Role** with the minimum permissions it needs (least privilege).
- No hardcoded credentials in the application. AWS IAM roles are used to authenticate between AWS services.
- Secrets (database passwords, encryption keys, API tokens) are stored in **AWS Secrets Manager** and injected into containers at runtime. They are never stored in environment files or container images.

---

## Security & compliance

### AWS certifications

Orb's infrastructure runs on AWS, which maintains the industry's most comprehensive compliance program. The services used by Orb (ECS, RDS, ElastiCache, CloudFront, S3, KMS) are covered by the following certifications:

| Certification | What it means |
|---|---|
| **SOC 1 Type II** | Controls over financial reporting are audited and verified by an independent third party. |
| **SOC 2 Type II** | Security, availability, processing integrity, confidentiality, and privacy controls are independently audited. |
| **SOC 3** | Public summary report of SOC 2 findings, available without an NDA. |
| **ISO 27001** | Information security management system (ISMS) certified by an accredited body. |
| **ISO 27017** | Cloud-specific security controls, beyond the baseline ISO 27001. |
| **ISO 27018** | Protection of personally identifiable information (PII) in cloud environments. |
| **ISO 9001** | Quality management processes certified. |

These certifications mean that the physical infrastructure, data center controls, and platform-level security Orb runs on have been independently verified to meet some of the most rigorous standards in the industry.

### Encryption summary

| Layer | At rest | In transit |
|---|---|---|
| Frontend (S3) | AES-256 (SSE-KMS) | TLS 1.2+ via CloudFront |
| API traffic | — | TLS 1.2+ via ALB + ACM |
| Database (Aurora) | AES-256 via KMS | TLS enforced |
| Cache (ElastiCache) | AES-256 | TLS enforced |
| Secrets | AES-256 via KMS (Secrets Manager) | TLS |
| Org config fields | Fernet (application-level, on top of RDS encryption) | TLS |

### Additional controls

- **AWS CloudTrail** — Every API call to AWS services is logged, creating a full audit trail of infrastructure changes.
- **Amazon GuardDuty** — Continuous threat detection. Monitors for unusual activity, unauthorized access attempts, and known threat patterns.
- **AWS Config** — Tracks configuration changes to AWS resources and flags deviations from security baselines.
- **Automated patching** — Fargate and managed services (RDS, ElastiCache) receive security patches from AWS automatically, with no manual intervention required.

---

## Connecting to your organization's systems

Orb needs to call your organization's internal APIs (SAP, CRM, ticketing, or any other system) to execute processes on behalf of users. The key challenge: how do we make that connection securely, without exposing your internal systems to the public internet?

Below are the recommended approaches, from lightest to most robust, depending on your organization's existing infrastructure.

---

### Option 1 — AWS Site-to-Site VPN

An encrypted tunnel is created between your on-premises network (or private cloud) and Orb's AWS VPC. Traffic flows through this tunnel and never touches the public internet.

**How it works:**
- Your network team configures a VPN gateway on your side.
- AWS creates a Virtual Private Gateway on Orb's VPC.
- The two are connected through an IPSec tunnel, encrypted end-to-end.
- Orb's ECS services can then reach your SAP or service layer over private IP addresses.

**Best for:** Organizations that already have VPN infrastructure or want a straightforward, cost-effective private connection.

**AWS service:** AWS Site-to-Site VPN

---

### Option 2 — AWS Direct Connect

A dedicated private network connection is provisioned between your data center (or office) and AWS — bypassing the public internet entirely. Direct Connect provides consistent bandwidth, lower latency, and stronger isolation than a VPN.

**How it works:**
- Your organization works with an AWS Direct Connect partner to provision a physical or virtual cross-connect into an AWS Direct Connect location.
- A private Virtual Interface (VIF) is created into Orb's VPC.
- Orb services call your systems over this dedicated link.

**Best for:** Organizations with high-volume integrations, strict latency requirements, or regulatory mandates around data not traversing the public internet.

**AWS service:** AWS Direct Connect

---

### Option 3 — AWS PrivateLink (recommended for SaaS-style exposure)

Your organization exposes its service layer as a **PrivateLink endpoint service**. Orb's VPC subscribes to this endpoint. Traffic between Orb and your systems flows entirely within the AWS network — no internet, no VPN, no firewall rules to open.

**How it works:**
- Your organization fronts its internal API with a Network Load Balancer (NLB) in your own AWS account.
- You create a VPC Endpoint Service backed by that NLB.
- You explicitly allowlist Orb's AWS account ID as an authorized consumer.
- Orb creates a VPC Interface Endpoint that connects to your service privately.
- Orb ECS tasks call your API over a private IP address inside the VPC.

**Why this is particularly strong:**
- Your service is never exposed to the internet, not even briefly.
- You control exactly which AWS accounts can connect — access is revocable at any time.
- No complex firewall rules or IP allowlisting needed on your end.
- Works even if your systems are in a different AWS account or region.

**Best for:** Organizations already on AWS, or those willing to front their service layer with an NLB. Lowest ongoing operational overhead once set up.

**AWS services:** AWS PrivateLink, VPC Endpoint Services, Network Load Balancer

---

### Option 4 — VPC Peering

If your organization's internal systems already run in an AWS VPC (in your own account), VPC peering creates a direct network route between your VPC and Orb's VPC. Traffic stays within AWS's internal network.

**How it works:**
- A peering connection is established between the two VPCs (yours and Orb's).
- Route tables are updated so traffic destined for your systems routes through the peering link.
- Security groups are updated to allow only the specific ECS task security groups to initiate connections.

**Best for:** Organizations already running their service layer on AWS.

**AWS service:** VPC Peering

---

### Comparison

| Option | Internet exposure | Complexity | Best fit |
|---|---|---|---|
| Site-to-Site VPN | None | Low–Medium | On-premises with existing VPN |
| Direct Connect | None | Medium–High | High-volume or compliance-driven |
| PrivateLink | None | Low (once set up) | AWS-hosted APIs, SaaS-style |
| VPC Peering | None | Low | Both sides already on AWS |

All four options share one guarantee: **your internal systems are never reachable from the public internet**. Orb's ECS services are the only authorized callers, and access can be revoked or restricted at any time by your network or cloud team.
