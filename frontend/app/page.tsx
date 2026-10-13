import { redirect } from "next/navigation";

// No landing page: the login page signs people in, or sends signed-in users to their home.
export default function Home() {
  redirect("/login");
}
