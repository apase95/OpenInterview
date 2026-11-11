import { HRScreen } from "../components/workspaces";
import { requireResource } from "../../lib/access";
export default async function Page() {
  const data = await requireResource("/hr", "/hr");
  return <HRScreen rooms={data.rooms} />;
}
