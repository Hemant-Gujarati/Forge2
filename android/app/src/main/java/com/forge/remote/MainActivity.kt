package com.forge.remote

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Code
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import com.forge.remote.data.ForgeApiClient
import com.forge.remote.data.PreferencesManager
import com.forge.remote.ui.screens.*
import com.forge.remote.ui.theme.ForgeRemoteTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val prefs = PreferencesManager(applicationContext)
        val apiClient = ForgeApiClient(prefs)

        setContent {
            ForgeRemoteTheme {
                var isPaired by remember { mutableStateOf(prefs.isPaired) }
                var selectedTab by remember { mutableIntStateOf(0) }
                var activeTaskId by remember { mutableStateOf<String?>(null) }

                if (!isPaired) {
                    PairScreen(
                        prefs = prefs,
                        apiClient = apiClient,
                        onPairSuccess = { isPaired = true }
                    )
                } else if (activeTaskId != null) {
                    TaskDetailScreen(
                        taskId = activeTaskId!!,
                        apiClient = apiClient,
                        onBack = { activeTaskId = null }
                    )
                } else {
                    Scaffold(
                        bottomBar = {
                            NavigationBar {
                                NavigationBarItem(
                                    selected = selectedTab == 0,
                                    onClick = { selectedTab = 0 },
                                    icon = { Icon(Icons.Default.Code, contentDescription = "Task") },
                                    label = { Text("Task") }
                                )
                                NavigationBarItem(
                                    selected = selectedTab == 1,
                                    onClick = { selectedTab = 1 },
                                    icon = { Icon(Icons.Default.CheckCircle, contentDescription = "Approvals") },
                                    label = { Text("Approvals") }
                                )
                                NavigationBarItem(
                                    selected = selectedTab == 2,
                                    onClick = { selectedTab = 2 },
                                    icon = { Icon(Icons.Default.History, contentDescription = "History") },
                                    label = { Text("History") }
                                )
                                NavigationBarItem(
                                    selected = selectedTab == 3,
                                    onClick = { selectedTab = 3 },
                                    icon = { Icon(Icons.Default.Settings, contentDescription = "Settings") },
                                    label = { Text("Settings") }
                                )
                            }
                        }
                    ) { innerPadding ->
                        Surface(modifier = Modifier.padding(innerPadding)) {
                            when (selectedTab) {
                                0 -> ChatTaskScreen(
                                    apiClient = apiClient,
                                    onTaskSubmitted = { submittedId -> activeTaskId = submittedId }
                                )
                                1 -> ApprovalsScreen(apiClient = apiClient)
                                2 -> RecentTasksScreen(
                                    apiClient = apiClient,
                                    onTaskClick = { clickedId -> activeTaskId = clickedId }
                                )
                                3 -> SettingsScreen(
                                    prefs = prefs,
                                    apiClient = apiClient,
                                    onUnpair = { isPaired = false }
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
