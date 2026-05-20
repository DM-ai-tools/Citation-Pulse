import type { Metadata } from "next";
import { LegalPage, LegalSection } from "@/components/legal/LegalPage";

export const metadata: Metadata = {
  title: "Privacy Policy · Citation Pulse",
  description: "How Citation Pulse and Traffic Radius collect, use, and protect your information.",
};

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy Policy" updated="19 May 2026">
      <LegalSection title="1. Who we are">
        <p>
          Citation Pulse is an AI visibility and GEO citation monitoring product operated by Traffic Radius
          (&quot;we&quot;, &quot;us&quot;). This policy explains how we handle personal information when you use
          citationpulse.com.au and related services (the &quot;Service&quot;).
        </p>
      </LegalSection>

      <LegalSection title="2. Information we collect">
        <p>
          <strong className="text-tr-navy">Account information:</strong> name, email address, and password (stored
          as a secure hash). We do not store plain-text passwords.
        </p>
        <p>
          <strong className="text-tr-navy">Scan and workspace data:</strong> URLs, brand names, competitor domains,
          prompts you submit, and citation results returned from AI engines (ChatGPT, Claude, Perplexity, Gemini)
          as part of running scans and reports.
        </p>
        <p>
          <strong className="text-tr-navy">Technical data:</strong> IP address, browser type, device information,
          cookies or session tokens used to keep you signed in, and server logs for security and troubleshooting.
        </p>
      </LegalSection>

      <LegalSection title="3. How we use information">
        <p>We use your information to:</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>create and manage your account and tenant workspace;</li>
          <li>run citation scans, generate reports, and show dashboard analytics;</li>
          <li>improve the Service, fix errors, and prevent abuse;</li>
          <li>send service-related notices (e.g. security or account updates); and</li>
          <li>comply with legal obligations.</li>
        </ul>
        <p>We do not sell your personal information to third parties.</p>
      </LegalSection>

      <LegalSection title="4. AI providers and subprocessors">
        <p>
          To perform scans, we send prompts and related context to third-party AI APIs (e.g. OpenAI, Anthropic,
          Google, Perplexity via our configured providers). Those providers process data under their own terms and
          privacy policies. We configure keys and routing to minimise unnecessary data sent with each request.
        </p>
      </LegalSection>

      <LegalSection title="5. Storage, security, and retention">
        <p>
          Data is stored on secure infrastructure (including databases hosted in controlled environments). We use
          encryption in transit (HTTPS), access controls, and hashed credentials. We retain account and scan data
          while your account is active and for a reasonable period afterward unless you request deletion or we are
          required to retain records by law.
        </p>
      </LegalSection>

      <LegalSection title="6. Your rights">
        <p>
          Depending on applicable law (including the Australian Privacy Act 1988), you may request access to, correction
          of, or deletion of personal information we hold about you. To make a request, email{" "}
          <a href="mailto:info@trafficradius.com.au" className="font-semibold text-brand-primary hover:underline">
            info@trafficradius.com.au
          </a>
          . We will respond within a reasonable time.
        </p>
      </LegalSection>

      <LegalSection title="7. Changes">
        <p>
          We may update this policy from time to time. The &quot;Last updated&quot; date at the top will change when we
          do. Continued use of the Service after changes constitutes acceptance of the updated policy.
        </p>
      </LegalSection>
    </LegalPage>
  );
}
