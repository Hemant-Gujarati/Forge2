package com.forge.remote.data

import com.google.gson.annotations.SerializedName

data class HealthResponse(
    val name: String,
    val version: String,
    val status: String,
    @SerializedName("default_provider") val defaultProvider: String,
    val model: String,
    @SerializedName("safe_mode") val safeMode: Boolean,
    val cwd: String
)

data class PairRequest(
    @SerializedName("pairing_token") val pairingToken: String,
    @SerializedName("client_name") val clientName: String
)

data class PairResponse(
    val status: String,
    val token: String?,
    @SerializedName("client_name") val clientName: String?,
    val message: String?,
    val error: String?
)

data class TaskSubmitRequest(
    val prompt: String
)

data class TaskSubmitResponse(
    @SerializedName("task_id") val taskId: String,
    val status: String,
    val prompt: String
)

data class TaskItem(
    val id: String,
    val prompt: String,
    val provider: String?,
    val model: String?,
    val status: String,
    val result: String?,
    @SerializedName("created_at") val createdAt: String?,
    @SerializedName("completed_at") val completedAt: String?
)

data class TasksResponse(
    val tasks: List<TaskItem>
)

data class ApprovalItem(
    val id: String,
    @SerializedName("task_id") val taskId: String?,
    @SerializedName("action_type") val actionType: String,
    @SerializedName("action_summary") val actionSummary: String,
    @SerializedName("action_payload") val actionPayload: Map<String, Any>?,
    val status: String,
    @SerializedName("created_at") val createdAt: String?
)

data class ApprovalsResponse(
    val approvals: List<ApprovalItem>
)

data class ActionResponse(
    val status: String,
    val error: String?
)
