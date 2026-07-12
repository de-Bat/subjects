import { openDB, type IDBPDatabase } from "idb";

export type QueueType =
  | "capture"
  | "approve"
  | "reject"
  | "reprocess"
  | "remove"
  | "category_create"
  | "category_delete"
  | "settings_update";

export interface CacheEntry {
  data: unknown;
  cachedAt: number;
}

export interface QueueEntry {
  id: number;
  type: QueueType;
  payload: unknown;
  createdAt: number;
}

const DB_NAME = "subjects-offline";
const DB_VERSION = 1;
const CACHE_STORE = "cache";
const QUEUE_STORE = "queue";

let dbPromise: Promise<IDBPDatabase> | null = null;
let db: IDBPDatabase | null = null;

function getDb(): Promise<IDBPDatabase> {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(database) {
        if (!database.objectStoreNames.contains(CACHE_STORE)) {
          database.createObjectStore(CACHE_STORE);
        }
        if (!database.objectStoreNames.contains(QUEUE_STORE)) {
          database.createObjectStore(QUEUE_STORE, { keyPath: "id", autoIncrement: true });
        }
      },
    }).then((database) => {
      db = database;
      return database;
    });
  }
  return dbPromise;
}

// Test-only: force a fresh connection after the underlying DB was deleted.
export function _resetDbHandle(): void {
  if (db) {
    db.close();
    db = null;
  }
  dbPromise = null;
}

export async function cacheGet(key: string): Promise<CacheEntry | undefined> {
  const db = await getDb();
  return db.get(CACHE_STORE, key);
}

export async function cacheSet(key: string, data: unknown): Promise<void> {
  const db = await getDb();
  await db.put(CACHE_STORE, { data, cachedAt: Date.now() }, key);
}

export async function cacheEntries(): Promise<Array<[string, CacheEntry]>> {
  const db = await getDb();
  const keys = await db.getAllKeys(CACHE_STORE);
  const values = await db.getAll(CACHE_STORE);
  return keys.map((k, i) => [String(k), values[i] as CacheEntry]);
}

export async function queueAdd(type: QueueType, payload: unknown): Promise<number> {
  const db = await getDb();
  const id = await db.add(QUEUE_STORE, { type, payload, createdAt: Date.now() });
  return id as number;
}

export async function queueAll(): Promise<QueueEntry[]> {
  const db = await getDb();
  return (await db.getAll(QUEUE_STORE)) as QueueEntry[];
}

export async function queueDelete(id: number): Promise<void> {
  const db = await getDb();
  await db.delete(QUEUE_STORE, id);
}
