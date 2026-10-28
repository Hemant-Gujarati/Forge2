package com.forge.remote.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.forge.remote.data.ForgeApiClient
import com.forge.remote.data.TaskItem
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun TaskDetailScreen(
    taskId: String,
    apiClient: ForgeApiClient,
    onBack: () -> Unit
) {
    var task by remember { mutableStateOf<TaskItem?>(null) }
    var isPolling by remember { mutableStateOf(true) }
    val scope = rememberCoroutineScope()

    // Poll task updates while running
    LaunchedEffect(taskId, isPolling) {
        while (isPolling) {
            apiClient.getTask(taskId).onSuccess {
                task = it
                if (it.status in listOf("done", "error", "cancelled")) {
                    isPolling = false
                }
            }
            delay(2000)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text("Task: $taskId", fontWeight = FontWeight.Bold, fontSize = 20.sp)
            if (task?.status == "running" || task?.status == "pending") {
                Button(
                    onClick = {
                        scope.launch {
                            apiClient.cancelTask(taskId)
                            isPolling = false
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error)
                ) {
                    Icon(Icons.Default.Close, contentDescription = "Cancel")
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Cancel")
                }
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Status chip
        val status = task?.status ?: "loading"
        val statusColor = when (status) {
            "done" -> MaterialTheme.colorScheme.primary
            "running" -> MaterialTheme.colorScheme.secondary
            "cancelled" -> MaterialTheme.colorScheme.error
            else -> MaterialTheme.colorScheme.onSurface
        }

        Text("Status: ${status.uppercase()}", color = statusColor, fontWeight = FontWeight.Bold)

        Spacer(modifier = Modifier.height(12.dp))

        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                Text("Prompt:", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                Text(task?.prompt ?: "...", fontSize = 14.sp)
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text("Execution Result / Logs:", fontWeight = FontWeight.Bold, fontSize = 14.sp)

        Card(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(12.dp)
                    .verticalScroll(rememberScrollState())
            ) {
                Text(
                    text = task?.result ?: if (status == "running") "Agent is working on your PC..." else "Waiting...",
                    fontFamily = FontFamily.Monospace,
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }
        }
    }
}
