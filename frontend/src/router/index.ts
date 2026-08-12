import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

declare module "vue-router" {
  interface RouteMeta {
    public?: boolean;
    permission?: string;
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("../views/LoginView.vue"), meta: { public: true } },
    {
      path: "/",
      component: () => import("../components/AppLayout.vue"),
      children: [
        { path: "", redirect: "/smart-query" },
        { path: "smart-query", name: "smart-query", component: () => import("../views/SmartQueryView.vue"), meta: { permission: "ai_query" } },
        { path: "workspace", name: "workspace", component: () => import("../views/WorkspaceView.vue"), meta: { permission: "workspace" } },
        { path: "connections", name: "connections", component: () => import("../views/ConnectionsView.vue"), meta: { permission: "connections" } },
        { path: "reports", name: "reports", component: () => import("../views/ReportsView.vue"), meta: { permission: "reports" } },
        { path: "users", name: "users", component: () => import("../views/UsersView.vue"), meta: { permission: "users" } },
        { path: "roles", name: "roles", component: () => import("../views/RolesView.vue"), meta: { permission: "roles" } },
        { path: "settings", name: "settings", component: () => import("../views/SettingsView.vue"), meta: { permission: "settings" } },
        { path: "audit", name: "audit", component: () => import("../views/AuditView.vue"), meta: { permission: "audit" } },
      ],
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.user) await auth.fetchMe();
  if (!to.meta.public && !auth.isLoggedIn) {
    return { path: "/login", query: { redirect: to.fullPath } };
  }
  if (to.path === "/login" && auth.isLoggedIn) {
    return { path: "/" + (auth.defaultHome() || "workspace") };
  }
  const permission = to.meta.permission;
  if (permission && !auth.hasPermission(permission)) {
    const home = auth.defaultHome();
    return { path: home ? "/" + home : "/login" };
  }
  return true;
});

export default router;