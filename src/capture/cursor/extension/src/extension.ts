// Copyright © 2025 Sierra Labs LLC
// SPDX-License-Identifier: AGPL-3.0-only
// License-Filename: LICENSE

/**
 * Blueplane Telemetry Extension for Cursor
 *
 * Main entry point for the VSCode extension.
 * Manages session lifecycle and database monitoring.
 */

import * as vscode from 'vscode';
import { SessionManager } from './sessionManager';
import { DatabaseMonitor } from './databaseMonitor';
import { QueueWriter } from './queueWriter';
import { ExtensionConfig } from './types';

let sessionManager: SessionManager;
let databaseMonitor: DatabaseMonitor;
let queueWriter: QueueWriter;
let statusBarItem: vscode.StatusBarItem;

/**
 * Extension activation
 */
export async function activate(context: vscode.ExtensionContext) {
  console.log('Blueplane Telemetry extension activating...');

  // Load configuration
  const config = loadConfiguration();

  if (!config.enabled) {
    console.log('Blueplane Telemetry is disabled');
    return;
  }

  // Initialize components
  queueWriter = new QueueWriter(config.redisHost, config.redisPort);
  sessionManager = new SessionManager(context, queueWriter);
  databaseMonitor = new DatabaseMonitor(queueWriter, sessionManager);

  // Initialize Redis connection
  const redisConnected = await queueWriter.initialize();
  if (!redisConnected) {
    vscode.window.showWarningMessage(
      'Blueplane: Could not connect to Redis. Telemetry will not be captured.'
    );
    return;
  }

  // Start new session
  sessionManager.startNewSession();

  // Start database monitoring if enabled
  if (config.databaseMonitoring) {
    const monitoringStarted = await databaseMonitor.startMonitoring();
    if (!monitoringStarted) {
      console.warn('Database monitoring could not be started');
    }
  }

  // Create status bar item
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusBarItem.text = '$(pulse) Blueplane';
  statusBarItem.tooltip = 'Blueplane Telemetry Active';
  statusBarItem.command = 'blueplane.showStatus';
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand('blueplane.showStatus', () => {
      sessionManager.showStatus();
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('blueplane.newSession', () => {
      sessionManager.stopSession();
      sessionManager.startNewSession();
      vscode.window.showInformationMessage('Started new Blueplane session');
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('blueplane.stopSession', () => {
      sessionManager.stopSession();
      vscode.window.showInformationMessage('Stopped Blueplane session');
    })
  );

  // Handle workspace changes
  context.subscriptions.push(
    vscode.workspace.onDidChangeWorkspaceFolders(() => {
      // Start new session for new workspace
      sessionManager.stopSession();
      sessionManager.startNewSession();
    })
  );

  console.log('Blueplane Telemetry extension activated successfully');
}

/**
 * Extension deactivation
 */
export async function deactivate() {
  console.log('Blueplane Telemetry extension deactivating...');

  // Stop monitoring
  if (databaseMonitor) {
    databaseMonitor.stopMonitoring();
  }

  // Stop session
  if (sessionManager) {
    sessionManager.stopSession();
  }

  // Disconnect from Redis
  if (queueWriter) {
    await queueWriter.disconnect();
  }

  // Hide status bar
  if (statusBarItem) {
    statusBarItem.hide();
    statusBarItem.dispose();
  }

  console.log('Blueplane Telemetry extension deactivated');
}

/**
 * Load configuration from VSCode settings
 */
function loadConfiguration(): ExtensionConfig {
  const config = vscode.workspace.getConfiguration('blueplane');

  return {
    enabled: config.get<boolean>('enabled', true),
    databaseMonitoring: config.get<boolean>('databaseMonitoring', true),
    redisHost: config.get<string>('redisHost', 'localhost'),
    redisPort: config.get<number>('redisPort', 6379),
  };
}
