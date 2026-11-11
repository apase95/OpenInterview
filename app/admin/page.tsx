import { AdminScreen } from "../components/workspaces";
import { requireResource } from "../../lib/access";
export default async function Page() {
  const data = await requireResource("/admin", "/admin");
  return <AdminScreen data={data} />;
}
