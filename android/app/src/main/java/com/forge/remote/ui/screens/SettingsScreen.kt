package com.forge.remote.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.forge.remote.data.ForgeApiClient
import com.forge.remote.data.HealthResponse
import com.forge.remote.data.PreferencesManager
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(
    prefs: PreferencesManager,
    apiClient: ForgeApiClient,
    onUnpair: () -> Unit
) {
    var health by remember { mutableStateOf<HealthResponse?>(null) }
    var connectionStatus by remember { mutableStateOf("Checking connection...") }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        apiClient.getHealth()
            .onSuccess {
                health = it
                connectionStatus = "Connected to ${it.name} v${it.version}"
            }
            .onFailure {
                connectionStatus = "Offline / Cannot reach desktop (${it.message})"
            }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        Text("Settings & Connection", fontWeight = FontWeight.Bold, fontSize = 20.sp)

        Spacer(modifier = Modifier.height(16.dp))

        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
        ) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text("Desktop Server URL:", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                Text(prefs.serverUrl, fontSize = 14.sp)

                Spacer(modifier = Modifier.height(12.dp))

                Text("Connection Status:", fontWeight = FontWeight.Bold, fontSize = 12.sp)
                Text(connectionStatus, fontSize = 14.sp, color = MaterialTheme.colorScheme.primary)

                if (health != null) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("AI Provider: ${health?.defaultProvider}", fontSize = 13.sp)
                    Text("Model: ${health?.model}", fontSize = 13.sp)
                    Text("Telegram Bot: ${if (health?.telegramEnabled == true) "Active" else "Not configured"}", fontSize = 13.sp)
                    Text("Working Directory: ${health?.cwd}", fontSize = 13.sp)
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        Button(
            onClick = {
                prefs.clear()
                onUnpair()
            },
            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Unpair from Desktop")
        }
    }
}
