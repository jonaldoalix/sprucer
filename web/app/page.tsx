import Link from "next/link";

export default function HomePage() {
  return (
    <section className="hero">
      <h1>Write applications you can defend.</h1>
      <p>
        Sprucer keeps a knowledge bank of facts you will stand behind, ingests a job
        description, and asks an OpenAI-compatible model to draft materials grounded only
        in that truth. Drafts stay drafts until you approve them.
      </p>
      <div className="actions">
        <Link className="btn" href="/applications">
          Open applications
        </Link>
        <Link className="btn secondary" href="/knowledge">
          Edit knowledge bank
        </Link>
      </div>
    </section>
  );
}
