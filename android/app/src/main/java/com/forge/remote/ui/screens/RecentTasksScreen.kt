package com.forge.remote.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.forge.remote.data.ForgeApiClient
import com.forge.remote.data.TaskItem
import kotlinx.coroutines.launch

@Composable
fun RecentTasksScreen(
    apiClient: ForgeApiClient,
    onTaskClick: (String) -> Unit
) {
    var tasks by remember { mutableStateOf<List<TaskItem>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    fun refresh() {
        scope.launch {
            isLoading = true
            apiClient.getTasks().onSuccess {
                tasks = it
            }
            isLoading = false
        }
    }

    LaunchedEffect(Unit) {
        refresh()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text("Recent Tasks", fontWeight = FontWeight.Bold, fontSize = 20.sp)
            IconButton(onClick = { refresh() }) {
                Text("🔄")
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        if (tasks.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = if (isLoading) "Loading tasks..." else "No tasks recorded yet.",
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(tasks) { task ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onTaskClick(task.id) },
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = "ID: ${task.id}",
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 12.sp,
                                    color = MaterialTheme.colorScheme.primary
                                )
                                Text(
                                    text = task.status.uppercase(),
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 12.sp,
                                    color = when (task.status) {
                                        "done" -> MaterialTheme.colorScheme.primary
                                        "running" -> MaterialTheme.colorScheme.secondary
                                        else -> MaterialTheme.colorScheme.error
                                    }
                                )
                            }
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = task.prompt,
                                maxLines = 2,
                                fontSize = 14.sp
                            )
                        }
                    }
                }
            }
        }
    }
}
