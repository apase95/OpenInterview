import { JoinScreen } from "../../components/candidate";
import { requireResource } from "../../../lib/access";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  await requireResource(`/rooms/${encodeURIComponent(id)}`, `/rooms/${id}`);
  return <JoinScreen id={id} />;
}
