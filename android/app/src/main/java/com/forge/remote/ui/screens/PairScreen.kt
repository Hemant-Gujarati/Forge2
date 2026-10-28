package com.forge.remote.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.forge.remote.data.ForgeApiClient
import com.forge.remote.data.PreferencesManager
import kotlinx.coroutines.launch

@Composable
fun PairScreen(
    prefs: PreferencesManager,
    apiClient: ForgeApiClient,
    onPairSuccess: () -> Unit
) {
    var serverUrl by remember { mutableStateOf(prefs.serverUrl) }
    var pairingToken by remember { mutableStateOf("") }
    var isLoading by remember { mutableStateOf(false) }
    var statusMessage by remember { mutableStateOf("") }
    var isError by remember { mutableStateOf(false) }

    val scope = rememberCoroutineScope()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text("🔨 FORGE", fontSize = 36.sp, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
        Text("Remote Desktop Controller", fontSize = 16.sp, color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))

        Spacer(modifier = Modifier.height(32.dp))

        OutlinedTextField(
            value = serverUrl,
            onValueChange = { serverUrl = it },
            label = { Text("Desktop URL (e.g. http://192.168.1.100:5000)") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )

        Spacer(modifier = Modifier.height(16.dp))

        OutlinedTextField(
            value = pairingToken,
            onValueChange = { pairingToken = it },
            label = { Text("Pairing Token (from PC config)") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password)
        )

        Spacer(modifier = Modifier.height(24.dp))

        Button(
            onClick = {
                scope.launch {
                    isLoading = true
                    statusMessage = "Connecting to desktop..."
                    isError = false
                    prefs.serverUrl = serverUrl

                    val result = apiClient.pair(pairingToken, android.os.Build.MODEL)
                    isLoading = false
                    result.onSuccess {
                        statusMessage = "Paired successfully!"
                        onPairSuccess()
                    }.onFailure {
                        isError = true
                        statusMessage = it.message ?: "Failed to pair with desktop"
                    }
                }
            },
            modifier = Modifier.fillMaxWidth(),
            enabled = !isLoading && serverUrl.isNotBlank()
        ) {
            if (isLoading) {
                CircularProgressIndicator(modifier = Modifier.size(24.dp), strokeWidth = 2.dp)
            } else {
                Text("Pair with Desktop")
            }
        }

        if (statusMessage.isNotEmpty()) {
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = statusMessage,
                color = if (isError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
                fontSize = 14.sp
            )
        }
    }
}
