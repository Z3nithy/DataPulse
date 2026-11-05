import {
  LayoutDashboard,
  PlugZap,
  UploadCloud,
  Database,
  ChartNoAxesCombined,
  Gauge,
  TrendingUp,
  Sparkles,
  FileChartColumn,
  Bell,
  Settings,
} from '@lucide/vue'

export const navigation = [
  { path: 'dashboard', label: 'Visão geral', icon: LayoutDashboard, group: 'Workspace' },
  { path: 'sources', label: 'Fontes de dados', icon: PlugZap, group: 'Workspace' },
  { path: 'datasets', label: 'Datasets', icon: Database, group: 'Workspace' },
  { path: 'ingestion', label: 'Importações', icon: UploadCloud, group: 'Workspace' },
  { path: 'analytics', label: 'Analytics', icon: ChartNoAxesCombined, group: 'Inteligência' },
  { path: 'kpis', label: 'KPIs', icon: Gauge, group: 'Inteligência' },
  { path: 'trends', label: 'Tendências', icon: TrendingUp, group: 'Inteligência' },
  { path: 'insights', label: 'Insights', icon: Sparkles, group: 'Inteligência' },
  { path: 'reports', label: 'Relatórios', icon: FileChartColumn, group: 'Inteligência' },
  { path: 'alerts', label: 'Alertas', icon: Bell, group: 'Gestão' },
  { path: 'settings', label: 'Configurações', icon: Settings, group: 'Gestão' },
]
