import type { ChatQueryResponse } from '@/types';

const mockResponses: Record<string, ChatQueryResponse> = {
  'gmp': {
    answer: `Good Manufacturing Practice (GMP) is a system of guidelines that ensures products are consistently produced and controlled according to quality standards. In the pharmaceutical context, GMP covers all aspects of production — from raw materials, premises, and equipment to the training and hygiene of staff.

**Key GMP principles applicable to Sothema's operations:**

1. **Documentation**: All manufacturing processes must be clearly defined, systematically reviewed, and shown to be capable of consistently manufacturing products of the required quality.
2. **Validation**: Critical steps of manufacturing processes must be validated, including any significant changes.
3. **Personnel**: Adequate trained personnel and premises must be provided.
4. **Records**: Records must be made during manufacture to show that all steps were taken as required.
5. **Deviation handling**: Any deviations must be fully recorded and investigated.

These requirements are outlined in WHO GMP guidelines, EU GMP Annex 15, and FDA 21 CFR Parts 210-211.`,
    sources: [
      { documentId: 'doc-001', documentTitle: 'SOP-QC-001: Analytical Method Validation for Active Substances', segmentContent: 'All analytical methods shall be validated in accordance with ICH Q2(R1) guidelines and GMP requirements before use in routine quality control testing...', chunkIndex: 2, relevanceScore: 0.92 },
      { documentId: 'doc-004', documentTitle: 'SOP-QC-004: Environmental Monitoring in Clean Rooms', segmentContent: 'Environmental monitoring procedures shall comply with EU GMP Annex 1 requirements for cleanroom classification and particle monitoring...', chunkIndex: 1, relevanceScore: 0.87 },
    ],
  },
  'ich': {
    answer: `The International Council for Harmonisation (ICH) provides guidelines that are critical for pharmaceutical compliance. Here are the key ICH guidelines relevant to Sothema's compliance framework:

**Quality Guidelines:**
- **ICH Q1A/Q1B**: Stability testing of new drug substances and products — defines storage conditions, testing intervals, and data evaluation
- **ICH Q2(R1)**: Validation of analytical procedures — covers specificity, linearity, accuracy, precision, and robustness
- **ICH Q7**: Good Manufacturing Practice for Active Pharmaceutical Ingredients — API production requirements
- **ICH Q10**: Pharmaceutical Quality System — lifecycle approach to quality management

**Efficacy Guidelines:**
- **ICH Q8**: Pharmaceutical Development — design space and critical quality attributes
- **ICH Q9**: Quality Risk Management — risk assessment tools (FMEA, HACCP)

These guidelines form the backbone of the compliance scoring system used in our analyses, particularly in the "Regulatory" category (max 25 points).`,
    sources: [
      { documentId: 'doc-005', documentTitle: 'REG-MA-001: Marketing Authorization Dossier — Amoxicillin 500mg', segmentContent: 'The dossier has been prepared in accordance with ICH M4 Common Technical Document (CTD) format. Module 3 contains the quality documentation including...', chunkIndex: 5, relevanceScore: 0.95 },
      { documentId: 'doc-001', documentTitle: 'SOP-QC-001: Analytical Method Validation for Active Substances', segmentContent: 'Validation parameters shall include specificity, linearity, range, accuracy, precision (repeatability and intermediate precision), detection limit, and quantitation limit as defined in ICH Q2(R1)...', chunkIndex: 3, relevanceScore: 0.91 },
    ],
  },
  'stability': {
    answer: `Stability testing is a critical component of pharmaceutical quality assurance. Based on our document analysis, here are the key requirements:

**ICH Q1A(R2) Stability Testing Requirements:**

| Condition | Temperature | Humidity | Duration |
|-----------|------------|----------|----------|
| Long-term | 25°C ± 2°C | 60% RH ± 5% | 12 months minimum |
| Intermediate | 30°C ± 2°C | 65% RH ± 5% | 6 months |
| Accelerated | 40°C ± 2°C | 75% RH ± 5% | 6 months |

**Key Requirements:**
1. At least 3 production batches must be tested
2. Testing should cover physical, chemical, biological, and microbiological attributes
3. Container closure system should be the same as proposed for marketing
4. Photostability testing per ICH Q1B is required for new substances
5. Significant change criteria must be pre-defined

Our compliance analysis found that SOP-QC-003 covers these requirements but could strengthen the section on photostability testing protocols.`,
    sources: [
      { documentId: 'doc-003', documentTitle: 'SOP-QC-003: Stability Testing Protocol for Finished Products', segmentContent: 'Stability studies shall be conducted according to ICH Q1A(R2) guidelines. Long-term, intermediate, and accelerated conditions shall be used for all finished product stability programs...', chunkIndex: 1, relevanceScore: 0.97 },
      { documentId: 'doc-007', documentTitle: 'REG-MA-003: Annual Product Review — Insulin Production Line', segmentContent: 'Annual stability data review shows all tested batches remain within specification at the 24-month timepoint under long-term storage conditions...', chunkIndex: 8, relevanceScore: 0.84 },
    ],
  },
  'validation': {
    answer: `Process validation ensures that a manufacturing process consistently produces a product meeting its predetermined specifications and quality attributes. Here's a summary based on our compliance documents:

**Three Stages of Process Validation (FDA Guidance 2011):**

1. **Stage 1 — Process Design**: Building and capturing process knowledge. Includes Design of Experiments (DoE), identification of Critical Quality Attributes (CQAs) and Critical Process Parameters (CPPs).

2. **Stage 2 — Process Qualification**: Confirming the process design. Includes Installation Qualification (IQ), Operational Qualification (OQ), and Performance Qualification (PQ). Typically requires 3 consecutive successful batches.

3. **Stage 3 — Continued Process Verification**: Ongoing assurance during routine production. Statistical process control, trending, and monitoring.

**Current Gaps Identified:**
Our analysis of VAL-PR-001 (Score: 65/100) found:
- Risk assessment (FMEA) not included in the protocol
- Continued process verification plan is missing
- Sampling plans lack statistical rationale
- Process capability indices (Cpk) not addressed

These gaps significantly impact the Regulatory (16/25) and Quality (16/25) scores.`,
    sources: [
      { documentId: 'doc-008', documentTitle: 'VAL-PR-001: Process Validation Protocol — Tablet Compression', segmentContent: 'This protocol defines the approach for validating the tablet compression process for the oral solid dosage manufacturing line. Critical process parameters include compression force, turret speed, and feeder speed...', chunkIndex: 0, relevanceScore: 0.96 },
      { documentId: 'doc-009', documentTitle: 'VAL-PR-002: Cleaning Validation Report — Oral Solid Dosage Line', segmentContent: 'Cleaning validation was performed following three consecutive cleaning cycles. Swab and rinse sampling methods were used to determine residual API levels...', chunkIndex: 2, relevanceScore: 0.82 },
    ],
  },
  'capa': {
    answer: `CAPA (Corrective and Preventive Action) is a fundamental element of the pharmaceutical quality system. Here's an overview based on our compliance documents:

**CAPA Process Flow:**
1. **Identification**: Record the deviation, complaint, or audit finding
2. **Evaluation**: Assess the risk and impact using severity classification
3. **Root Cause Analysis**: Use tools like 5-Why, Ishikawa diagram, or FMEA
4. **Action Plan**: Define corrective actions (fix the problem) and preventive actions (prevent recurrence)
5. **Implementation**: Execute with assigned responsibilities and timelines
6. **Effectiveness Check**: Verify the actions resolved the issue
7. **Closure**: Document completion and update relevant SOPs

**Regulatory References:**
- FDA 21 CFR 211.192 — Investigation of discrepancies
- ICH Q10 — Pharmaceutical Quality System (CAPA as a key enabler)
- EU GMP Chapter 1 — Quality management principles

**Gap Noted:** Our analysis of SOP-QC-002 (Score: 72/100) found that deviation handling is not fully linked to the CAPA system, affecting the traceability score (17/25).`,
    sources: [
      { documentId: 'doc-010', documentTitle: 'AUD-INT-001: Internal Audit Report — Warehouse & Storage Compliance', segmentContent: 'CAPA recommendations included for each finding. CAPA effectiveness verification planned with 90-day follow-up reviews...', chunkIndex: 4, relevanceScore: 0.88 },
      { documentId: 'doc-002', documentTitle: 'SOP-QC-002: Raw Material Sampling and Testing Procedures', segmentContent: 'Deviations during sampling or testing shall be documented and reported to the QA department. However, the current procedure does not specify linkage to the CAPA system...', chunkIndex: 7, relevanceScore: 0.85 },
    ],
  },
};

const defaultResponse: ChatQueryResponse = {
  answer: `I can help you with pharmaceutical compliance and regulatory questions. Based on the documents in our system, I can provide information about:

- **GMP (Good Manufacturing Practice)** requirements and guidelines
- **ICH guidelines** (Q1-Q10) for quality, stability, and validation
- **FDA regulations** (21 CFR Parts 210-211)
- **Process validation** protocols and requirements
- **CAPA** (Corrective and Preventive Action) procedures
- **Stability testing** requirements and conditions
- **Analytical method validation** (ICH Q2)
- **Regulatory submissions** and CTD format
- **Audit findings** and compliance scoring

Please ask a specific question and I'll search our compliance document library for relevant information.`,
  sources: [],
};

export function getMockChatResponse(query: string): ChatQueryResponse {
  const q = query.toLowerCase();

  if (q.includes('gmp') || q.includes('good manufacturing') || q.includes('manufacturing practice')) {
    return mockResponses['gmp'];
  }
  if (q.includes('ich') || q.includes('harmonisation') || q.includes('harmonization')) {
    return mockResponses['ich'];
  }
  if (q.includes('stability') || q.includes('shelf life') || q.includes('storage condition')) {
    return mockResponses['stability'];
  }
  if (q.includes('validation') || q.includes('process qualification') || q.includes('cpk')) {
    return mockResponses['validation'];
  }
  if (q.includes('capa') || q.includes('corrective') || q.includes('preventive') || q.includes('deviation')) {
    return mockResponses['capa'];
  }

  return defaultResponse;
}

export const suggestedQuestions = [
  'What are the key GMP requirements for pharmaceutical manufacturing?',
  'Which ICH guidelines are most relevant to our compliance framework?',
  'What are the stability testing requirements under ICH Q1A?',
  'Explain the three stages of process validation',
  'How should CAPA procedures be implemented according to regulations?',
];
