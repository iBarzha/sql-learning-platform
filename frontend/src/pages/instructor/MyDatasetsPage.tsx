import { useState, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import { Database, Plus, Upload, Edit, Trash2, Play, Sparkles } from 'lucide-react';
import datasetsApi, { type Dataset, type DatasetPreviewResult } from '@/api/datasets';
import {
  useMyDatasets,
  useCreateDataset,
  useUpdateDataset,
  useDeleteDataset,
} from '@/hooks/queries/useDatasets';
import { SqlEditor } from '@/components/editor/SqlEditor';
import { getApiErrorMessage } from '@/lib/utils';
import { useAuthStore } from '@/store/authStore';

const DB_TYPES = [
  { value: 'sqlite', label: 'SQLite' },
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'mariadb', label: 'MariaDB' },
  { value: 'mongodb', label: 'MongoDB' },
  { value: 'redis', label: 'Redis' },
];

interface FormState {
  id?: string;
  name: string;
  description: string;
  database_type: string;
  schema_sql: string;
  seed_sql: string;
}

const emptyForm: FormState = {
  name: '',
  description: '',
  database_type: 'sqlite',
  schema_sql: '',
  seed_sql: '',
};

export function MyDatasetsPage() {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'admin';

  const { data: datasets = [], isLoading, error } = useMyDatasets();
  const createMutation = useCreateDataset();
  const [editingId, setEditingId] = useState<string | undefined>();
  const updateMutation = useUpdateDataset(editingId ?? '');
  const deleteMutation = useDeleteDataset();

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [apiError, setApiError] = useState('');
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [previewDataset, setPreviewDataset] = useState<Dataset | null>(null);
  const [previewResult, setPreviewResult] = useState<DatasetPreviewResult | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // AI generation state
  const [showGenerator, setShowGenerator] = useState(false);
  const [genTopic, setGenTopic] = useState('');
  const [genSize, setGenSize] = useState<'small' | 'medium' | 'large'>('medium');
  const [genDbType, setGenDbType] = useState('sqlite');
  const [genLoading, setGenLoading] = useState(false);
  const [genError, setGenError] = useState('');

  function openNew() {
    setForm(emptyForm);
    setEditingId(undefined);
    setApiError('');
    setShowForm(true);
  }

  function openEdit(ds: Dataset) {
    setForm({
      id: ds.id,
      name: ds.name,
      description: ds.description || '',
      database_type: ds.database_type,
      schema_sql: ds.schema_sql,
      seed_sql: ds.seed_sql || '',
    });
    setEditingId(ds.id);
    setApiError('');
    setShowForm(true);
  }

  async function handleSave() {
    setApiError('');
    try {
      if (editingId) {
        await updateMutation.mutateAsync({
          name: form.name,
          description: form.description,
          database_type: form.database_type,
          schema_sql: form.schema_sql,
          seed_sql: form.seed_sql,
        });
      } else {
        await createMutation.mutateAsync({
          name: form.name,
          description: form.description,
          database_type: form.database_type,
          schema_sql: form.schema_sql,
          seed_sql: form.seed_sql,
        });
      }
      setShowForm(false);
    } catch (err) {
      setApiError(getApiErrorMessage(err, 'Failed to save dataset'));
    }
  }

  async function handleUpload(file: File) {
    setApiError('');
    try {
      const { schema_sql, seed_sql } = await datasetsApi.uploadSql(file);
      setForm({
        ...emptyForm,
        name: file.name.replace(/\.(sql|txt)$/i, ''),
        schema_sql,
        seed_sql,
      });
      setEditingId(undefined);
      setShowForm(true);
    } catch (err) {
      setApiError(getApiErrorMessage(err, 'Failed to parse SQL file'));
    }
  }

  async function handlePreview(ds: Dataset) {
    setPreviewDataset(ds);
    setPreviewResult(null);
    setPreviewLoading(true);
    try {
      const result = await datasetsApi.preview(ds.id);
      setPreviewResult(result);
    } catch (err) {
      const msg = getApiErrorMessage(err, 'Preview failed');
      setPreviewResult({ success: false, error_message: msg });
    } finally {
      setPreviewLoading(false);
    }
  }

  async function confirmDelete() {
    if (!deleteId) return;
    try {
      await deleteMutation.mutateAsync(deleteId);
    } finally {
      setDeleteId(null);
    }
  }

  async function handleGenerate() {
    setGenError('');
    setGenLoading(true);
    try {
      const result = await datasetsApi.generate({
        topic: genTopic,
        size: genSize,
        database_type: genDbType,
      });
      // Prefill the create form with the AI output
      setForm({
        name: result.name,
        description: result.description,
        database_type: genDbType,
        schema_sql: result.schema_sql,
        seed_sql: result.seed_sql,
      });
      setEditingId(undefined);
      setShowGenerator(false);
      setShowForm(true);
    } catch (err) {
      setGenError(getApiErrorMessage(err, 'Generation failed'));
    } finally {
      setGenLoading(false);
    }
  }

  const myDatasets = datasets.filter((d) => isAdmin ? true : !d.created_by || d.created_by === user?.id);
  const grouped = {
    own: myDatasets.filter((d) => d.created_by === user?.id),
    system: myDatasets.filter((d) => !d.created_by),
    others: isAdmin ? myDatasets.filter((d) => d.created_by && d.created_by !== user?.id) : [],
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{getApiErrorMessage(error, 'Failed to load datasets')}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Database className="h-6 w-6" />
            My Datasets
          </h1>
          <p className="text-muted-foreground">
            Reusable schemas and seed data for your courses
          </p>
        </div>
        <div className="flex gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".sql,.txt"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleUpload(file);
              e.target.value = '';
            }}
          />
          <Button variant="outline" onClick={() => fileInputRef.current?.click()}>
            <Upload className="h-4 w-4 mr-2" />
            Upload SQL
          </Button>
          <Button variant="outline" onClick={() => { setGenError(''); setShowGenerator(true); }}>
            <Sparkles className="h-4 w-4 mr-2" />
            Generate with AI
          </Button>
          <Button onClick={openNew}>
            <Plus className="h-4 w-4 mr-2" />
            New Dataset
          </Button>
        </div>
      </div>

      {apiError && (
        <Alert variant="destructive">
          <AlertDescription>{apiError}</AlertDescription>
        </Alert>
      )}

      <DatasetSection title="Your datasets" datasets={grouped.own} onEdit={openEdit} onDelete={(id) => setDeleteId(id)} onPreview={handlePreview} canManage emptyText="You haven't created any datasets yet." />

      {grouped.system.length > 0 && (
        <DatasetSection title="System datasets" datasets={grouped.system} onPreview={handlePreview} />
      )}

      {isAdmin && grouped.others.length > 0 && (
        <DatasetSection title="Other instructors' datasets" datasets={grouped.others} onEdit={openEdit} onDelete={(id) => setDeleteId(id)} onPreview={handlePreview} canManage />
      )}

      {/* Create/Edit dialog */}
      <Dialog open={showForm} onOpenChange={(o) => !o && setShowForm(false)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingId ? 'Edit Dataset' : 'New Dataset'}</DialogTitle>
            <DialogDescription>
              Define schema and seed SQL. This dataset becomes selectable in lesson exercises.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Name *</Label>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g., Library System" />
              </div>
              <div className="space-y-2">
                <Label>Database Type *</Label>
                <Select value={form.database_type} onValueChange={(v) => setForm({ ...form, database_type: v })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DB_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="What's in this dataset?" />
            </div>
            <div className="space-y-2">
              <Label>Schema SQL (CREATE TABLE / ALTER / DROP)</Label>
              <SqlEditor
                value={form.schema_sql}
                onChange={(v) => setForm({ ...form, schema_sql: v })}
                height="160px"
                placeholder="CREATE TABLE users (...);"
              />
            </div>
            <div className="space-y-2">
              <Label>Seed SQL (INSERT statements)</Label>
              <SqlEditor
                value={form.seed_sql}
                onChange={(v) => setForm({ ...form, seed_sql: v })}
                height="160px"
                placeholder="INSERT INTO users VALUES ...;"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button
              onClick={handleSave}
              disabled={!form.name.trim() || !form.schema_sql.trim() || createMutation.isPending || updateMutation.isPending}
            >
              {(createMutation.isPending || updateMutation.isPending) && <Spinner size="sm" className="mr-2" />}
              {editingId ? 'Save Changes' : 'Create Dataset'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Preview dialog */}
      <Dialog open={!!previewDataset} onOpenChange={(o) => !o && setPreviewDataset(null)}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{previewDataset?.name}</DialogTitle>
            <DialogDescription>
              {previewDataset?.description || 'Dataset preview'}
            </DialogDescription>
          </DialogHeader>
          {previewLoading ? (
            <div className="flex justify-center py-8"><Spinner /></div>
          ) : previewResult ? (
            previewResult.success === false || previewResult.error_message ? (
              <Alert variant="destructive">
                <AlertDescription className="font-mono text-xs">
                  {previewResult.error_message}
                </AlertDescription>
              </Alert>
            ) : (
              <div className="space-y-3">
                <div className="text-xs text-muted-foreground">
                  {previewResult.row_count} rows · {previewResult.execution_time_ms}ms
                </div>
                <div className="overflow-auto border rounded-md">
                  <table className="text-sm w-full">
                    <thead className="bg-muted">
                      <tr>
                        {previewResult.columns?.map((c, i) => (
                          <th key={i} className="px-3 py-2 text-left font-medium border-b">{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {previewResult.rows?.slice(0, 50).map((row, ri) => (
                        <tr key={ri} className="border-b">
                          {(row as unknown[]).map((cell, ci) => (
                            <td key={ci} className="px-3 py-2 font-mono text-xs">
                              {cell === null ? <span className="text-muted-foreground italic">NULL</span> : String(cell)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )
          ) : null}
        </DialogContent>
      </Dialog>

      {/* AI Generator dialog */}
      <Dialog open={showGenerator} onOpenChange={(o) => !o && !genLoading && setShowGenerator(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5" />
              Generate Dataset with AI
            </DialogTitle>
            <DialogDescription>
              Describe what you want and Gemini will generate matching schema + seed data.
              You can edit the result before saving.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {genError && (
              <Alert variant="destructive">
                <AlertDescription>{genError}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label>Topic *</Label>
              <Textarea
                value={genTopic}
                onChange={(e) => setGenTopic(e.target.value)}
                placeholder="e.g., A small bookstore with customers, books, authors and orders. Include returns and bestseller flags."
                rows={3}
                disabled={genLoading}
              />
              <p className="text-xs text-muted-foreground">
                Describe entities, relationships, and any specific data you want to see.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Size</Label>
                <Select value={genSize} onValueChange={(v) => setGenSize(v as 'small' | 'medium' | 'large')} disabled={genLoading}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="small">Small (~10 rows)</SelectItem>
                    <SelectItem value="medium">Medium (~50 rows)</SelectItem>
                    <SelectItem value="large">Large (~200 rows)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Database Type</Label>
                <Select value={genDbType} onValueChange={setGenDbType} disabled={genLoading}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DB_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowGenerator(false)} disabled={genLoading}>
              Cancel
            </Button>
            <Button onClick={handleGenerate} disabled={!genTopic.trim() || genLoading}>
              {genLoading ? <Spinner size="sm" className="mr-2" /> : <Sparkles className="h-4 w-4 mr-2" />}
              {genLoading ? 'Generating...' : 'Generate'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={!!deleteId} onOpenChange={(o) => !o && setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Dataset</DialogTitle>
            <DialogDescription>
              This permanently deletes the dataset. Lessons that reference it will lose the link.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>Cancel</Button>
            <Button variant="destructive" onClick={confirmDelete} disabled={deleteMutation.isPending}>
              {deleteMutation.isPending && <Spinner size="sm" className="mr-2" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

interface SectionProps {
  title: string;
  datasets: Dataset[];
  onEdit?: (ds: Dataset) => void;
  onDelete?: (id: string) => void;
  onPreview: (ds: Dataset) => void;
  canManage?: boolean;
  emptyText?: string;
}

function DatasetSection({ title, datasets, onEdit, onDelete, onPreview, canManage, emptyText }: SectionProps) {
  return (
    <Card variant="glass">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{datasets.length} datasets</CardDescription>
      </CardHeader>
      <CardContent>
        {datasets.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-6">{emptyText ?? 'No datasets'}</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {datasets.map((ds) => (
              <div key={ds.id} className="rounded-xl border border-border/60 p-4 space-y-2 bg-card/50">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold truncate">{ds.name}</h3>
                    <p className="text-xs text-muted-foreground line-clamp-2">{ds.description || '—'}</p>
                  </div>
                  <Badge variant="outline" className="shrink-0 text-xs">{ds.database_type}</Badge>
                </div>
                {ds.created_by_name && (
                  <p className="text-xs text-muted-foreground">by {ds.created_by_name}</p>
                )}
                <div className="flex items-center gap-1 pt-2">
                  <Button variant="ghost" size="sm" onClick={() => onPreview(ds)}>
                    <Play className="h-3 w-3 mr-1" />
                    Preview
                  </Button>
                  {canManage && onEdit && (
                    <Button variant="ghost" size="sm" onClick={() => onEdit(ds)}>
                      <Edit className="h-3 w-3 mr-1" />
                      Edit
                    </Button>
                  )}
                  {canManage && onDelete && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => onDelete(ds.id)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
