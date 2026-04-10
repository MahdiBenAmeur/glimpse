import { Search, Users, Heart, FolderOpen, Bookmark, Database, Settings, ChevronLeft } from "lucide-react";
import { NavLink } from "@/components/NavLink";
import { useApp } from "@/contexts/AppContext";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarFooter,
  useSidebar,
} from "@/components/ui/sidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const navItems = [
  { title: "Search", url: "/search", icon: Search },
  { title: "People", url: "/people", icon: Users },
  { title: "Favorites", url: "/favorites", icon: Heart },
  { title: "Collections", url: "/collections", icon: FolderOpen },
  { title: "Saved Searches", url: "/saved-searches", icon: Bookmark },
  { title: "Index", url: "/index-manager", icon: Database },
  { title: "Settings", url: "/settings", icon: Settings },
];

export function AppSidebar() {
  const { state, toggleSidebar } = useSidebar();
  const collapsed = state === "collapsed";
  const { activeModel, indexingStatus, lastIndexedTime } = useApp();

  const indexFresh = lastIndexedTime
    ? (Date.now() - new Date(lastIndexedTime).getTime()) < 86400000
    : false;

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border">
      <SidebarContent className="pt-4">
        {!collapsed && (
          <div className="px-4 pb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center">
                <Search className="w-3.5 h-3.5 text-primary-foreground" />
              </div>
              <span className="font-semibold text-sm text-foreground">Glimpse One</span>
            </div>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={toggleSidebar}>
              <ChevronLeft className="w-4 h-4" />
            </Button>
          </div>
        )}

        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    {collapsed ? (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <NavLink to={item.url} className="hover:bg-sidebar-accent" activeClassName="bg-sidebar-accent text-sidebar-accent-foreground font-medium">
                            <item.icon className="w-4 h-4" />
                          </NavLink>
                        </TooltipTrigger>
                        <TooltipContent side="right">{item.title}</TooltipContent>
                      </Tooltip>
                    ) : (
                      <NavLink to={item.url} className="hover:bg-sidebar-accent" activeClassName="bg-sidebar-accent text-sidebar-accent-foreground font-medium">
                        <item.icon className="w-4 h-4 mr-2" />
                        <span>{item.title}</span>
                      </NavLink>
                    )}
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-3 space-y-2">
        {!collapsed && (
          <>
            {activeModel && (
              <div className="flex items-center gap-1.5">
                <Badge variant="secondary" className="text-[10px] font-normal truncate">
                  {activeModel.name}
                </Badge>
              </div>
            )}
            <div className="flex items-center gap-1.5">
              <div className={`w-1.5 h-1.5 rounded-full ${indexingStatus.phase !== "idle" && indexingStatus.phase !== "complete" ? "bg-warning animate-pulse" : indexFresh ? "bg-success" : "bg-muted-foreground"}`} />
              <span className="text-[10px] text-muted-foreground">
                {indexingStatus.phase !== "idle" && indexingStatus.phase !== "complete"
                  ? `Indexing... ${indexingStatus.progress}%`
                  : indexFresh ? "Index up to date" : "Index outdated"}
              </span>
            </div>
            <span className="text-[9px] text-muted-foreground/60">v0.1.0</span>
          </>
        )}
      </SidebarFooter>
    </Sidebar>
  );
}
