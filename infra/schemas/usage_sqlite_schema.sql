CREATE TABLE IF NOT EXISTS usage_assignments(host TEXT,thread TEXT,cut TEXT,phase TEXT,owner TEXT,
      start TEXT,end TEXT,parent TEXT,PRIMARY KEY(host,thread,start));

CREATE TABLE IF NOT EXISTS usage_collection(host TEXT PRIMARY KEY,receipt TEXT);

CREATE TABLE IF NOT EXISTS usage_diagnostics(kind TEXT PRIMARY KEY,count INTEGER);

CREATE TABLE IF NOT EXISTS usage_occurrences(provider TEXT,response_id TEXT,host TEXT,thread TEXT,
      source TEXT,PRIMARY KEY(provider,response_id,host,thread,source));

CREATE TABLE IF NOT EXISTS usage_parents(host TEXT,thread TEXT,parent TEXT,born TEXT,
      PRIMARY KEY(host,thread));

CREATE TABLE IF NOT EXISTS usage_responses(provider TEXT,response_id TEXT,timestamp TEXT,
      model TEXT,usage TEXT,fingerprint TEXT,quarantined INTEGER DEFAULT 0,PRIMARY KEY(provider,response_id));

CREATE TABLE IF NOT EXISTS usage_sources(host TEXT,path TEXT,device INTEGER,inode INTEGER,
      offset INTEGER,prefix TEXT,anchor TEXT,metadata TEXT,primed INTEGER,PRIMARY KEY(host,path));

CREATE TABLE IF NOT EXISTS usage_windows(host TEXT PRIMARY KEY,start TEXT);
