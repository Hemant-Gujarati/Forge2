package com.forge.remote.data

import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttp
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

class ForgeApiClient(private val prefs: PreferencesManager) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .build()

    private val gson = Gson()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    suspend fun getHealth(): Result<HealthResponse> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("${prefs.serverUrl}/health")
                .get()
                .build()
            val response = client.newCall(request).execute()
            if (response.isSuccessful) {
                val body = response.body?.string() ?: ""
                val health = gson.fromJson(body, HealthResponse::class.java)
                Result.success(health)
            } else {
                Result.failure(Exception("HTTP ${response.code}: ${response.message}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun pair(pairingToken: String, clientName: String = "Android Remote"): Result<PairResponse> =
        withContext(Dispatchers.IO) {
            try {
                val payload = gson.toJson(PairRequest(pairingToken, clientName))
                val request = Request.Builder()
                    .url("${prefs.serverUrl}/v1/pair")
                    .post(payload.toRequestBody(jsonMediaType))
                    .build()
                val response = client.newCall(request).execute()
                val body = response.body?.string() ?: ""
                val pairResp = gson.fromJson(body, PairResponse::class.java)

                if (response.isSuccessful && pairResp.token != null) {
                    prefs.authToken = pairResp.token
                    Result.success(pairResp)
                } else {
                    Result.failure(Exception(pairResp.error ?: "Pairing failed (${response.code})"))
                }
            } catch (e: Exception) {
                Result.failure(e)
            }
        }

    suspend fun submitTask(prompt: String): Result<TaskSubmitResponse> = withContext(Dispatchers.IO) {
        try {
            val payload = gson.toJson(TaskSubmitRequest(prompt))
            val request = Request.Builder()
                .url("${prefs.serverUrl}/v1/tasks")
                .header("Authorization", "Bearer ${prefs.authToken}")
                .post(payload.toRequestBody(jsonMediaType))
                .build()
            val response = client.newCall(request).execute()
            if (response.isSuccessful) {
                val body = response.body?.string() ?: ""
                val task = gson.fromJson(body, TaskSubmitResponse::class.java)
                Result.success(task)
            } else {
                Result.failure(Exception("Error ${response.code}: ${response.body?.string()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getTasks(): Result<List<TaskItem>> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("${prefs.serverUrl}/v1/tasks")
                .header("Authorization", "Bearer ${prefs.authToken}")
                .get()
                .build()
            val response = client.newCall(request).execute()
            if (response.isSuccessful) {
                val body = response.body?.string() ?: ""
                val tasksResp = gson.fromJson(body, TasksResponse::class.java)
                Result.success(tasksResp.tasks)
            } else {
                Result.failure(Exception("Error ${response.code}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getTask(taskId: String): Result<TaskItem> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("${prefs.serverUrl}/v1/tasks/$taskId")
                .header("Authorization", "Bearer ${prefs.authToken}")
                .get()
                .build()
            val response = client.newCall(request).execute()
            if (response.isSuccessful) {
                val body = response.body?.string() ?: ""
                val task = gson.fromJson(body, TaskItem::class.java)
                Result.success(task)
            } else {
                Result.failure(Exception("Task not found (${response.code})"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun cancelTask(taskId: String): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("${prefs.serverUrl}/v1/tasks/$taskId/cancel")
                .header("Authorization", "Bearer ${prefs.authToken}")
                .post("{}".toRequestBody(jsonMediaType))
                .build()
            val response = client.newCall(request).execute()
            Result.success(response.isSuccessful)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getApprovals(): Result<List<ApprovalItem>> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("${prefs.serverUrl}/v1/approvals")
                .header("Authorization", "Bearer ${prefs.authToken}")
                .get()
                .build()
            val response = client.newCall(request).execute()
            if (response.isSuccessful) {
                val body = response.body?.string() ?: ""
                val approvalsResp = gson.fromJson(body, ApprovalsResponse::class.java)
                Result.success(approvalsResp.approvals)
            } else {
                Result.failure(Exception("Error ${response.code}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun approveAction(approvalId: String): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("${prefs.serverUrl}/v1/approvals/$approvalId/approve")
                .header("Authorization", "Bearer ${prefs.authToken}")
                .post("{}".toRequestBody(jsonMediaType))
                .build()
            val response = client.newCall(request).execute()
            Result.success(response.isSuccessful)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun rejectAction(approvalId: String): Result<Boolean> = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("${prefs.serverUrl}/v1/approvals/$approvalId/reject")
                .header("Authorization", "Bearer ${prefs.authToken}")
                .post("{}".toRequestBody(jsonMediaType))
                .build()
            val response = client.newCall(request).execute()
            Result.success(response.isSuccessful)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
