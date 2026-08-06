import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("../views/LoginView.vue"), meta: { public: true } },
    {
      path: "/",
      component: () => import("../components/AppLayout.vue"),
      children: [
        { path: "", redirect: "/workspace" },
        { path: "workspace", name: "workspace", component: () => import("../views/WorkspaceView.vue") },
        { path: "connections", name: "connections", component: () => import("../views/ConnectionsView.vue") },
        { path: "reports", name: "reports", component: () => import("../views/ReportsView.vue") },
        { path: "settings", name: "settings", component: () => import("../views/SettingsView.vue") },
        { path: "audit", name: "audit", component: () => import("../views/AuditView.vue") },
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
    return { path: "/workspace" };
  }
  return true;
});

export default router;
