package com.forge.remote.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.forge.remote.data.ForgeApiClient
import com.forge.remote.data.HealthResponse
import kotlinx.coroutines.launch

@Composable
fun ChatTaskScreen(
    apiClient: ForgeApiClient,
    onTaskSubmitted: (String) -> Unit
) {
    var prompt by remember { mutableStateOf("") }
    var healthInfo by remember { mutableStateOf<HealthResponse?>(null) }
    var isSubmitting by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf("") }

    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        apiClient.getHealth().onSuccess { healthInfo = it }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        // Status header
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                Text(
                    text = "PC Runtime Status",
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    color = MaterialTheme.colorScheme.primary
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Provider: ${healthInfo?.defaultProvider ?: "Connecting..."} | Model: ${healthInfo?.model ?: "..."}",
                    fontSize = 12.sp
                )
                Text(
                    text = "Safe Mode: ${if (healthInfo?.safeMode == true) "ON (Requires Approval)" else "OFF"}",
                    fontSize = 12.sp,
                    color = if (healthInfo?.safeMode == true) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "Instruct Forge Agent",
            fontWeight = FontWeight.Bold,
            fontSize = 18.sp
        )
        Text(
            text = "The AI runs on your PC and can inspect code, write files, run tests, and execute git commands.",
            fontSize = 13.sp,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
        )

        Spacer(modifier = Modifier.weight(1f))

        if (errorMessage.isNotEmpty()) {
            Text(
                text = errorMessage,
                color = MaterialTheme.colorScheme.error,
                fontSize = 13.sp,
                modifier = Modifier.padding(bottom = 8.dp)
            )
        }

        // Input row
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = prompt,
                onValueChange = { prompt = it },
                placeholder = { Text("e.g. Add unit tests for the auth module...") },
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(24.dp),
                maxLines = 4
            )

            Spacer(modifier = Modifier.width(8.dp))

            IconButton(
                onClick = {
                    if (prompt.isNotBlank() && !isSubmitting) {
                        scope.launch {
                            isSubmitting = true
                            errorMessage = ""
                            val res = apiClient.submitTask(prompt)
                            isSubmitting = false
                            res.onSuccess {
                                val submittedId = it.taskId
                                prompt = ""
                                onTaskSubmitted(submittedId)
                            }.onFailure {
                                errorMessage = it.message ?: "Failed to submit task"
                            }
                        }
                    }
                },
                modifier = Modifier
                    .size(50.dp)
                    .background(MaterialTheme.colorScheme.primary, RoundedCornerShape(25.dp)),
                enabled = prompt.isNotBlank() && !isSubmitting
            ) {
                if (isSubmitting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        color = MaterialTheme.colorScheme.onPrimary,
                        strokeWidth = 2.dp
                    )
                } else {
                    Icon(
                        Icons.Default.Send,
                        contentDescription = "Send",
                        tint = MaterialTheme.colorScheme.onPrimary
                    )
                }
            }
        }
    }
}
