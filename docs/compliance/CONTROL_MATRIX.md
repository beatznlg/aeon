# AEON OS — Compliance Control Matrix

Framework-to-control mapping tracked by the assurance evidence ledger. Coverage status per control is computed at runtime (see /compliance/frameworks); this matrix documents the mapping itself.

| Framework | Kind | Controls |
| --- | --- | --- |
| CJIS Security Policy (cjis) | government | CJIS agreement review; Segmentation & failover test; Immutable audit-log integrity; KMS/HSM-backed secret management |
| DORA (EU) (dora) | regulated | DORA operational-resilience review; RTO/RPO measurement; Incident-response exercise; Backup & restore drill; Segmentation & failover test |
| FedRAMP (fedramp) | government | FedRAMP boundary, SSP, 3PAO assessment; ATO / agency authorization; Independent security / penetration assessment; Immutable audit-log integrity; KMS/HSM-backed secret management; Backup & restore drill; Incident-response exercise |
| HIPAA (HITECH) (hipaa) | regulated | HIPAA risk analysis; Business associate agreement; ePHI data-flow validation; Immutable audit-log integrity; KMS/HSM-backed secret management; Incident-response exercise |
| ISO/IEC 27001 (iso27001) | audit | Independent security / penetration assessment; Immutable audit-log integrity; KMS/HSM-backed secret management; Incident-response exercise; Backup & restore drill |
| PCI DSS (pci_dss) | regulated | PCI DSS scope / QSA or SAQ validation; Independent security / penetration assessment; Immutable audit-log integrity; KMS/HSM-backed secret management |
| SOC 2 (soc2) | audit | Independent security / penetration assessment; Immutable audit-log integrity; KMS/HSM-backed secret management; Backup & restore drill; RTO/RPO measurement; Incident-response exercise |

## Control registry

| Control | Frameworks |
| --- | --- |
| ATO / agency authorization (ato_or_agency_authorization) | fedramp |
| Immutable audit-log integrity (audit_integrity) | cjis, fedramp, hipaa, iso27001, pci_dss, soc2 |
| Authority approval (authority_approval) |  |
| Business associate agreement (baa_review) | hipaa |
| Backup & restore drill (backup_restore) | dora, fedramp, iso27001, soc2 |
| CJIS agreement review (cjis_agreement_review) | cjis |
| DORA operational-resilience review (dora_resilience_review) | dora |
| ePHI data-flow validation (ephi_data_flow_validation) | hipaa |
| FedRAMP boundary, SSP, 3PAO assessment (fedramp_boundary_ssp_3pao) | fedramp |
| Financial model risk review (financial_model_risk_review) |  |
| HIPAA risk analysis (hipaa_risk_analysis) | hipaa |
| Incident-response exercise (incident_response_exercise) | dora, fedramp, hipaa, iso27001, soc2 |
| KMS/HSM-backed secret management (kms_validation) | cjis, fedramp, hipaa, iso27001, pci_dss, soc2 |
| PCI DSS scope / QSA or SAQ validation (pci_scope_qsa_or_saq) | pci_dss |
| RTO/RPO measurement (rto_rpo_measurement) | dora, soc2 |
| Critical-infrastructure safety case (safety_case_review) |  |
| Independent security / penetration assessment (security_assessment) | fedramp, iso27001, pci_dss, soc2 |
| Segmentation & failover test (segmentation_failover_test) | cjis, dora |
