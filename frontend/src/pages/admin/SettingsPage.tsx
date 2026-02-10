import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Settings, Database, Users, Server, ExternalLink } from 'lucide-react';

export function SettingsPage() {
  const { t } = useTranslation('admin');

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-3xl font-bold">{t('settings.title')}</h1>
        <p className="text-muted-foreground">{t('settings.subtitle')}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              {t('status.title')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span>{t('status.apiServer')}</span>
              <Badge variant="success">{t('status.online')}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span>{t('status.database')}</span>
              <Badge variant="success">{t('status.connected')}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span>{t('status.sandboxPool')}</span>
              <Badge variant="secondary">{t('status.available', { count: 3 })}</Badge>
            </div>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              {t('dbInfo.title')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span>{t('dbInfo.type')}</span>
              <span className="text-muted-foreground">PostgreSQL</span>
            </div>
            <div className="flex items-center justify-between">
              <span>{t('dbInfo.host')}</span>
              <span className="text-muted-foreground">localhost:5433</span>
            </div>
            <div className="flex items-center justify-between">
              <span>{t('dbInfo.databaseName')}</span>
              <span className="text-muted-foreground">sql_learning</span>
            </div>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              {t('quickActions.title')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <a
              href="http://localhost:8000/admin/"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button variant="outline" className="w-full justify-start">
                <ExternalLink className="h-4 w-4 mr-2" />
                {t('quickActions.djangoAdmin')}
              </Button>
            </a>
            <a
              href="http://localhost:8000/api/"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button variant="outline" className="w-full justify-start">
                <ExternalLink className="h-4 w-4 mr-2" />
                {t('quickActions.apiBrowser')}
              </Button>
            </a>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              {t('config.title')}
            </CardTitle>
            <CardDescription>
              {t('config.subtitle')}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {t('config.description')}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
