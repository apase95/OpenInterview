import AuthCard from "../auth-ui/AuthCard";
import { returnPath } from "../../lib/return-path";
export default async function Login({
  searchParams,
}: {
  searchParams: Promise<{ return_to?: string }>;
}) {
  const query = await searchParams;
  return (
    <AuthCard
      returnTo={query.return_to ? returnPath(query.return_to) : "/roles"}
    />
  );
}
