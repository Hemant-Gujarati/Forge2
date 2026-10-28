package com.forge.remote.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.forge.remote.data.ApprovalItem
import com.forge.remote.data.ForgeApiClient
import com.forge.remote.ui.theme.ApprovedGreen
import com.forge.remote.ui.theme.RejectedRed
import kotlinx.coroutines.launch

@Composable
fun ApprovalsScreen(
    apiClient: ForgeApiClient
) {
    var approvals by remember { mutableStateOf<List<ApprovalItem>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    fun refresh() {
        scope.launch {
            isLoading = true
            apiClient.getApprovals().onSuccess {
                approvals = it
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
            Text("Pending Approvals", fontWeight = FontWeight.Bold, fontSize = 20.sp)
            IconButton(onClick = { refresh() }) {
                Text("🔄")
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        if (approvals.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = if (isLoading) "Checking approvals..." else "✅ No pending approvals.\nSafe mode is protecting your PC.",
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                items(approvals) { item ->
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
                    ) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text(
                                text = "Action: ${item.actionType}",
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.primary,
                                fontSize = 14.sp
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = item.actionSummary,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Medium
                            )

                            if (!item.actionPayload.isNullOrEmpty()) {
                                Spacer(modifier = Modifier.height(8.dp))
                                Text(
                                    text = item.actionPayload.toString(),
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 11.sp,
                                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                                )
                            }

                            Spacer(modifier = Modifier.height(16.dp))

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.End
                            ) {
                                Button(
                                    onClick = {
                                        scope.launch {
                                            apiClient.rejectAction(item.id)
                                            refresh()
                                        }
                                    },
                                    colors = ButtonDefaults.buttonColors(containerColor = RejectedRed)
                                ) {
                                    Text("Reject")
                                }

                                Spacer(modifier = Modifier.width(8.dp))

                                Button(
                                    onClick = {
                                        scope.launch {
                                            apiClient.approveAction(item.id)
                                            refresh()
                                        }
                                    },
                                    colors = ButtonDefaults.buttonColors(containerColor = ApprovedGreen)
                                ) {
                                    Text("Approve")
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
