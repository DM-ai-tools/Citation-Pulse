import type { Metadata } from "next";
import { LegalPage, LegalSection } from "@/components/legal/LegalPage";

export const metadata: Metadata = {
  title: "Terms of Service · Citation Pulse",
  description: "Terms governing use of the Citation Pulse platform by Traffic Radius.",
};

export default function TermsPage() {
  return (
    <LegalPage title="Terms of Service" updated="19 May 2026">
      <LegalSection title="1. Agreement">
        <p>
          By accessing or using Citation Pulse (the &quot;Service&quot;), operated by Traffic Radius, you agree to
          these Terms. If you do not agree, do not use the Service. If you use the Service on behalf of an
          organisation, you represent that you have authority to bind that organisation.
        </p>
      </LegalSection>

      <LegalSection title="2. The Service">
        <p>
          Citation Pulse monitors how brands appear in AI-generated answers by running prompts against supported AI
          engines and analysing citations. Features, engines, and limits may change. We strive for accuracy but do not
          guarantee that AI outputs or our analysis are complete, current, or error-free.
        </p>
      </LegalSection>

      <LegalSection title="3. Accounts">
        <p>
          You must provide accurate registration details and keep your password confidential. You are responsible for
          activity under your account. Notify us promptly at{" "}
          <a href="mailto:info@trafficradius.com.au" className="font-semibold text-brand-primary hover:underline">
            info@trafficradius.com.au
          </a>{" "}
          if you suspect unauthorised access.
        </p>
      </LegalSection>

      <LegalSection title="4. Acceptable use">
        <p>You agree not to:</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>use the Service for unlawful purposes or to violate third-party rights;</li>
          <li>attempt to probe, disrupt, or gain unauthorised access to our systems;</li>
          <li>resell or redistribute the Service without written permission; or</li>
          <li>submit malicious URLs, excessive automated traffic, or content designed to harm providers or users.</li>
        </ul>
      </LegalSection>

      <LegalSection title="5. Intellectual property">
        <p>
          We own the Service, software, branding, and documentation. You retain rights to data you submit (e.g. brand
          names, URLs). You grant us a licence to use submitted data solely to operate and improve the Service.
        </p>
      </LegalSection>

      <LegalSection title="6. Disclaimers and liability">
        <p>
          The Service is provided &quot;as is&quot; to the maximum extent permitted by law. We disclaim implied
          warranties of merchantability, fitness for a particular purpose, and non-infringement. To the extent permitted
          by law, our total liability for any claim arising from these Terms or the Service is limited to the fees you
          paid us in the twelve (12) months before the claim (or AUD $100 if no fees were paid).
        </p>
      </LegalSection>

      <LegalSection title="7. Governing law">
        <p>
          These Terms are governed by the laws of Victoria, Australia. Courts in Victoria have exclusive jurisdiction,
          subject to any non-excludable consumer rights under Australian law.
        </p>
      </LegalSection>

      <LegalSection title="8. Changes">
        <p>
          We may modify these Terms by posting an updated version on this page. Material changes will be indicated by
          updating the date above. Your continued use after changes constitutes acceptance.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
