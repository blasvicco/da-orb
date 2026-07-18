# Orb — Security Summary

This document is a plain-language overview of how Orb protects your organization's data and how it connects to your internal systems without putting them at risk.

---

## Your data is private by design

Orb is built so that your data never touches the public internet unless absolutely necessary. The application, the database, the cache, and all the internal processing components live inside a locked private network in the cloud. From the outside, the only thing visible is the chat interface your employees use — nothing else.

Every piece of data Orb stores — conversations, user sessions, organization settings — is encrypted both when it is saved and when it travels between systems. Encryption is enforced automatically; there is no way to turn it off or bypass it.

Credentials and sensitive configuration values are never stored in code or configuration files. They are kept in a secure vault (AWS Secrets Manager) and only made available to the specific services that need them, at runtime.

---

## Built on a platform organizations trust

Orb runs on **Amazon Web Services (AWS)**, which holds some of the most rigorous independent security certifications in the industry:

- **SOC 2 Type II** — An independent auditor has verified that AWS's security, availability, and confidentiality controls work as claimed, on an ongoing basis.
- **SOC 1 Type II** — Controls relevant to financial reporting have been independently verified.
- **ISO 27001** — The international gold standard for information security management, certified by an accredited body.
- **ISO 27017** — Additional cloud-specific security controls on top of ISO 27001.
- **ISO 27018** — Specific protections for personal data stored in the cloud.

These are not self-assessments. They are audits carried out by independent third parties, renewed on a regular basis. When Orb runs on AWS, your organization inherits the security guarantees of that infrastructure.

---

## Access is limited to what is strictly necessary

Every component of Orb follows the principle of least privilege: each service can only access the resources it specifically needs, and nothing more. The database, for example, can only be reached by Orb's own application services — not from the internet, not from other internal tools, not even from within the cloud environment unless explicitly permitted.

All activity is logged. Every infrastructure change, every network connection, and every access attempt is recorded and available for audit.

---

## Connecting to your internal systems — without exposing them

For Orb to execute processes on your behalf — creating a purchase order, updating a record, triggering a workflow — it needs to be able to call your organization's internal APIs or service layer. This raises a fair question: does that mean opening up your systems to the internet?

**No. It does not.**

There are several well-established ways to give Orb access to your internal systems while keeping those systems completely invisible to the outside world. The right choice depends on your existing infrastructure.

---

### The options, in plain terms

**Encrypted tunnel (VPN)**
Your network team creates an encrypted tunnel between your on-premises environment and Orb's private cloud network. Traffic between Orb and your systems travels through this tunnel — it never touches the public internet. This is the simplest option if your organization already uses VPN infrastructure.

**Dedicated private connection (Direct Connect)**
A physical or virtual private link is established between your data center and AWS. Unlike a VPN, this is not a tunnel over the internet — it is a dedicated line that bypasses the public internet entirely. This option offers more consistent performance and is preferred for high-volume integrations or stricter compliance requirements.

**Private endpoint (PrivateLink) — recommended**
Your organization publishes its service layer as a private endpoint inside AWS. Orb connects to it over AWS's internal network — no internet involved, no firewall rules to open, no IP addresses to allowlist. You control exactly which systems are allowed to connect, and you can revoke access at any time. Your service layer remains completely invisible to the outside world; only explicitly authorized consumers can even see it exists.

**Direct network link (VPC Peering)**
If your organization's systems already run in AWS, a direct network connection can be established between your cloud environment and Orb's. Traffic stays within AWS's internal network and never leaves it.

---

### What all options have in common

Regardless of which approach your organization chooses:

- Your internal systems are **never exposed to the public internet**.
- Only Orb's specific application services are authorized to make calls — no other system, user, or service can reach your APIs through this connection.
- Access is **revocable at any time** by your network or cloud team.
- All traffic between Orb and your systems is **encrypted in transit**.

The goal is a connection that is as narrow and controlled as possible: Orb can call what it needs to, and nothing else can get through.
