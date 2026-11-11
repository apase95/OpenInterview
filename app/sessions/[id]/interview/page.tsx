import { redirect } from "next/navigation";
import { InterviewScreen } from "../../../components/candidate";
import { requireResource } from "../../../../lib/access";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const session = await requireResource(
    `/sessions/${encodeURIComponent(id)}`,
    `/sessions/${id}/interview`,
  );
  if (session.ended_at) redirect("/roles?ended=1");
  return <InterviewScreen id={id} />;
}
